import React, { useEffect, useMemo, useState } from 'react';
import type { QuickSetQuestion, QuickSetSession, QuickSetStep } from '../types/domain';
import { runScenario, getSession, answerQuestion } from '../services/quicksetService';

const defaultForm = {
  testerId: '',
  stbIp: '',
  apiKey: ''
};

const formatDateTime = (value?: string | null): string => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`;
};

const formatLogPreview = (value?: string | null, maxLines = 500): string => {
  if (!value) return 'No logs yet.';
  const lines = value.split(/\r?\n/);
  if (lines.length <= maxLines) {
    return value;
  }
  return [
    `Showing last ${maxLines} lines of ${lines.length} total.`,
    ...lines.slice(-maxLines)
  ].join('\n');
};

const getStepInfo = (step: QuickSetStep): string => {
  const metadata = (step.metadata ?? {}) as Record<string, unknown>;
  const fields = ['analysis', 'message', 'prompt', 'instruction', 'instructions', 'info'];
  for (const field of fields) {
    const value = metadata[field];
    if (typeof value === 'string' && value.trim()) {
      return value;
    }
  }
  if (typeof metadata.error === 'string' && metadata.error.trim()) {
    return `Error: ${metadata.error}`;
  }
  return '';
};

const getStatusClass = (label: string): string => {
  const normalized = label.toUpperCase();
  if (normalized === 'PASS') return 'status-pill status-pill--pass';
  if (normalized === 'FAIL') return 'status-pill status-pill--fail';
  if (normalized === 'RUNNING') return 'status-pill status-pill--running';
  if (normalized === 'AWAITING INPUT') return 'status-pill status-pill--running';
  if (normalized === 'INCONCLUSIVE') return 'status-pill status-pill--info';
  if (normalized === 'INFO') return 'status-pill status-pill--info';
  return 'status-pill';
};

const getInfraStatusClass = (status: string): string => {
  const normalized = status.toUpperCase();
  if (normalized === 'OK') return 'status-pill status-pill--pass';
  if (normalized === 'FAIL') return 'status-pill status-pill--fail';
  return 'status-pill status-pill--info';
};

const isYes = (value?: string): boolean => {
  if (!value) return false;
  return value.trim().toLowerCase() === 'yes';
};

const getAnswerValue = (answerStep?: QuickSetStep): string => {
  const metadata = (answerStep?.metadata ?? {}) as Record<string, unknown>;
  const value = metadata.answer;
  if (typeof value === 'string') {
    return value;
  }
  if (typeof value === 'number') {
    return String(value);
  }
  return '';
};

const shouldDisplayInfraStep = (step: QuickSetStep): boolean => {
  const statusLower = (step.status || '').toLowerCase();
  if (statusLower === 'fail') {
    return true;
  }
  const metadata = (step.metadata ?? {}) as Record<string, unknown>;
  const metaStatus = typeof metadata.status === 'string' ? metadata.status.toLowerCase() : '';
  const metaResult = typeof metadata.result === 'string' ? metadata.result.toLowerCase() : '';
  return (
    metaStatus === 'fail' ||
    metaStatus === 'error' ||
    metaResult === 'fail' ||
    metaResult === 'error'
  );
};

const extractQuestionId = (step: QuickSetStep): string | null => {
  const metadata = (step.metadata ?? {}) as Record<string, unknown>;
  const metaId = metadata.question_id;
  if (typeof metaId === 'string' && metaId.trim()) {
    return metaId.trim();
  }
  const name = step.name || '';
  if (name.startsWith('question_')) {
    const withoutPrefix = name.replace(/^question_/, '');
    if (withoutPrefix.endsWith('_answer')) {
      return withoutPrefix.replace(/_answer$/, '');
    }
    return withoutPrefix;
  }
  return null;
};

const shouldDisplayStep = (step: QuickSetStep): boolean => {
  const name = step.name || '';
  if (!name) return false;

  // מוסתר לגמרי לפי הדרישה
  if (name === 'log_analysis_complete' || name === 'tester_questions') {
    return false;
  }

  const metadata = (step.metadata ?? {}) as Record<string, unknown>;
  if (metadata.tester_visible === false) {
    return false;
  }

  const questionId = extractQuestionId(step);

  // לא מציגים את שורות ה־*_answer
  if (name.endsWith('_answer')) {
    return false;
  }

  // לא מציגים את volume_probe כשורה נפרדת, הוא מחובר ל־tv_osd_seen
  if (questionId === 'volume_probe') {
    return false;
  }

  // כל ה־question_* עצמם מוצגים (למעט החריגים למעלה)
  if (name.startsWith('question_')) {
    return true;
  }

  // analysis_summary תמיד מוצג
  if (name === 'analysis_summary') {
    return true;
  }

  // infra steps → מוצגים רק אם באמת חשוב (כשל)
  if (name.startsWith('adb_') || name.startsWith('logcat_')) {
    return shouldDisplayInfraStep(step);
  }

  // INFO steps לא־infra מוצגים רק אם יש בהם מידע
  const statusLower = (step.status || '').toLowerCase();
  if (statusLower === 'info') {
    return Boolean(getStepInfo(step));
  }

  // כל השאר: מוצג
  return true;
};

type AnswerMap = Map<string, QuickSetStep>;
type StepRow = { step: QuickSetStep; status: string; infoText: string };

const getQuestionStatus = (
  questionId: string,
  session: QuickSetSession | null,
  answerMap: AnswerMap
): string => {
  const sessionEnded = Boolean(session?.end_time);
  const answerValue = getAnswerValue(answerMap.get(questionId));
  const hasAnswer = Boolean(answerValue.trim());

  switch (questionId) {
    // ידני / notes – לא קובע PASS/FAIL
    case 'manual_trigger':
    case 'notes':
      return hasAnswer || sessionEnded ? 'INFO' : 'AWAITING INPUT';

    // tv_volume_changed – פשוט: yes = PASS, no = FAIL (אם הוזן)
    case 'tv_volume_changed':
      if (!hasAnswer) {
        return sessionEnded ? 'INFO' : 'AWAITING INPUT';
      }
      return isYes(answerValue) ? 'PASS' : 'FAIL';

    // tv_osd_seen – משולב עם volume_probe
    case 'tv_osd_seen': {
      const probeAnswer = getAnswerValue(answerMap.get('volume_probe'));
      const hasProbe = Boolean(probeAnswer.trim());
      if (!hasAnswer || !hasProbe) {
        return sessionEnded ? 'FAIL' : 'AWAITING INPUT';
      }
      return isYes(answerValue) && isYes(probeAnswer) ? 'PASS' : 'FAIL';
    }

    // pairing_screen_seen – דרישה קריטית
    case 'pairing_screen_seen':
      if (!hasAnswer) {
        return sessionEnded ? 'FAIL' : 'AWAITING INPUT';
      }
      return isYes(answerValue) ? 'PASS' : 'FAIL';

    // tv_brand_ui – יש/אין ערך
    case 'tv_brand_ui':
      if (!hasAnswer) {
        return sessionEnded ? 'FAIL' : 'AWAITING INPUT';
      }
      return answerValue.trim().length > 0 ? 'PASS' : 'FAIL';

    default:
      // ברירת מחדל – התנהגות עדינה: אם אין תשובה והסשן רץ → AWAITING INPUT
      if (!hasAnswer && !sessionEnded) {
        return 'AWAITING INPUT';
      }
      // אחרת INFO בלבד
      return 'INFO';
  }
};

const getDisplayStatus = (
  step: QuickSetStep,
  session: QuickSetSession | null,
  answerMap: AnswerMap
): string => {
  const raw = (step.status || '').toLowerCase();
  const hasEnded = Boolean(session?.end_time);
  const sessionResult = (session?.result || '').toLowerCase();

  // analysis_summary צריך לשקף את תוצאת הסשן
  if (step.name === 'analysis_summary' && (sessionResult === 'pass' || sessionResult === 'fail')) {
    return sessionResult.toUpperCase();
  }

  const questionId = extractQuestionId(step);
  if (questionId) {
    return getQuestionStatus(questionId, session, answerMap);
  }

  // לפני סוף הבדיקה – סטטוס "חי"
  if (!hasEnded) {
    if (!raw) return 'RUNNING';
    if (raw === 'info' || raw === 'running') return 'INFO';
    return raw.toUpperCase();
  }

  // אחרי סוף הבדיקה – אם יש PASS/FAIL מקומי, נכבד אותו
  if (raw === 'pass' || raw === 'fail') {
    return raw.toUpperCase();
  }

  // אחרת, הכל INFO
  if (raw === 'running' || raw === 'info' || !raw) {
    return 'INFO';
  }

  return raw.toUpperCase();
};

const buildStaticInfoText = (
  step: QuickSetStep,
  answerMap: AnswerMap,
  questionStepMap: Map<string, QuickSetStep>
): string => {
  const questionId = extractQuestionId(step);
  if (questionId) {
    const metadata = (step.metadata ?? {}) as Record<string, unknown>;
    const prompt = typeof metadata.prompt === 'string' ? metadata.prompt : '';
    const answerValue = getAnswerValue(answerMap.get(questionId));

    // tv_osd_seen → מוסיף לתיאור גם את volume_probe
    if (questionId === 'tv_osd_seen') {
      const probeStep = questionStepMap.get('volume_probe');
      const probeMeta = (probeStep?.metadata ?? {}) as Record<string, unknown>;
      const probePrompt = typeof probeMeta.prompt === 'string' ? probeMeta.prompt : '';
      const probeAnswer = getAnswerValue(answerMap.get('volume_probe'));

      const lines: string[] = [];
      if (prompt) lines.push(prompt);
      lines.push(`Answer: ${answerValue || '—'}`);
      if (probePrompt) {
        lines.push(`Volume probe: ${probePrompt}`);
      }
      lines.push(`Probe answer: ${probeAnswer || '—'}`);
      return lines.join('\n');
    }

    const lines: string[] = [];
    if (prompt) lines.push(prompt);
    lines.push(`Answer: ${answerValue || '—'}`);
    return lines.join('\n');
  }

  if (step.name === 'analysis_summary') {
    const metadata = (step.metadata ?? {}) as Record<string, unknown>;
    if (typeof metadata.analysis === 'string' && metadata.analysis.trim()) {
      return metadata.analysis.trim();
    }
  }

  if (step.name.startsWith('adb_') || step.name.startsWith('logcat_')) {
    const metadata = (step.metadata ?? {}) as Record<string, unknown>;
    const message = typeof metadata.message === 'string' ? metadata.message : '';
    const error = typeof metadata.error === 'string' ? metadata.error : '';
    if (message) return message;
    if (error) return `Error: ${error}`;
  }

  return getStepInfo(step) || '';
};

const QuickSetRunner: React.FC = () => {
  const [form, setForm] = useState(defaultForm);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [activeApiKey, setActiveApiKey] = useState<string | null>(null);
  const [session, setSession] = useState<QuickSetSession | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [pollError, setPollError] = useState<string | null>(null);
  const [answerError, setAnswerError] = useState<string | null>(null);
  const [answerText, setAnswerText] = useState('');
  const [isAnswerSubmitting, setIsAnswerSubmitting] = useState(false);
  const pendingQuestion = session?.pending_question ?? null;

  const scenarioName = 'TV_AUTO_SYNC' as const;

  const handleChange =
    (field: keyof typeof form) =>
    (event: React.ChangeEvent<HTMLInputElement>) => {
      setForm((prev) => ({ ...prev, [field]: event.target.value }));
    };

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitError(null);
    setPollError(null);

    if (!form.testerId || !form.stbIp || !form.apiKey) {
      setSubmitError('Tester ID, STB IP, and API key are required.');
      return;
    }

    try {
      setIsSubmitting(true);
      const response = await runScenario({
        testerId: form.testerId,
        stbIp: form.stbIp,
        apiKey: form.apiKey,
        scenarioName
      });
      setSessionId(response.session_id);
      setActiveApiKey(form.apiKey);
      setSession(null);
      setAnswerText('');
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : 'Failed to run scenario');
    } finally {
      setIsSubmitting(false);
    }
  };

  // polling על ה־session
  useEffect(() => {
    if (!sessionId || !activeApiKey) {
      return () => {};
    }

    let cancelled = false;
    let intervalId: number | undefined;

    const fetchSession = async () => {
      try {
        const data = await getSession(sessionId, activeApiKey);
        if (cancelled) {
          return;
        }
        setSession(data);
        if (data.result && data.result !== 'pending' && data.result !== 'running') {
          if (intervalId) {
            window.clearInterval(intervalId);
            intervalId = undefined;
          }
        }
      } catch (error) {
        if (!cancelled) {
          setPollError('Failed to fetch session status');
          if (intervalId) {
            window.clearInterval(intervalId);
            intervalId = undefined;
          }
        }
      }
    };

    fetchSession();
    intervalId = window.setInterval(fetchSession, 1500);

    return () => {
      cancelled = true;
      if (intervalId) {
        window.clearInterval(intervalId);
      }
    };
  }, [sessionId, activeApiKey]);

  useEffect(() => {
    setAnswerText('');
  }, [pendingQuestion?.id]);

  const resultLabel = useMemo(() => {
    if (!session) {
      return sessionId ? 'RUNNING' : '—';
    }

    if (session.state === 'awaiting_input') {
      return 'AWAITING INPUT';
    }

    if (session.state === 'running') {
      return 'RUNNING';
    }

    if (session.state === 'completed' && session.result) {
      return session.result.toUpperCase();
    }

    if (session.result) {
      return session.result.toUpperCase();
    }

    return (session.state || 'RUNNING').toUpperCase();
  }, [session, sessionId]);

  const steps: QuickSetStep[] = session?.steps ?? [];

  const answerMap = useMemo<AnswerMap>(() => {
    const map = new Map<string, QuickSetStep>();
    steps.forEach((step) => {
      const questionId = extractQuestionId(step);
      if (!questionId) return;
      if (step.name.endsWith('_answer')) {
        map.set(questionId, step);
      }
    });
    return map;
  }, [steps]);

  const questionStepMap = useMemo(() => {
    const map = new Map<string, QuickSetStep>();
    steps.forEach((step) => {
      const questionId = extractQuestionId(step);
      if (!questionId) return;
      if (!step.name.endsWith('_answer')) {
        map.set(questionId, step);
      }
    });
    return map;
  }, [steps]);

  const timelineRows = useMemo<StepRow[]>(() => {
    if (!steps.length) {
      return [];
    }
    const filtered = steps.filter(shouldDisplayStep);
    const dedupe = new Set<string>();
    const rows: StepRow[] = [];

    filtered.forEach((step) => {
      const statusLabel = getDisplayStatus(step, session, answerMap);
      const infoText = buildStaticInfoText(step, answerMap, questionStepMap);
      const timestampKey = step.timestamp ? new Date(step.timestamp).toISOString() : 'no-ts';
      const dedupeKey = `${step.name}|${statusLabel}|${timestampKey}|${infoText}`;
      if (dedupe.has(dedupeKey)) {
        return;
      }
      dedupe.add(dedupeKey);
      rows.push({ step, status: statusLabel, infoText });
    });

    return rows;
  }, [steps, session, answerMap, questionStepMap]);

  const submitAnswer = async (value: string) => {
    if (!sessionId || !activeApiKey || !pendingQuestion || isAnswerSubmitting) {
      return;
    }
    try {
      setAnswerError(null);
      setIsAnswerSubmitting(true);
      // 🔧 פה היה הבאג – חזרה לחתימה הנכונה:
      // answerQuestion(sessionId, apiKey, value) שמחזיר Session מעודכן
      const updated = await answerQuestion(sessionId, activeApiKey, value);
      setSession(updated);
      setAnswerText('');
    } catch (error) {
      setAnswerError(error instanceof Error ? error.message : 'Failed to send answer');
    } finally {
      setIsAnswerSubmitting(false);
    }
  };

  const renderQuestionControls = (question: QuickSetQuestion) => {
    const disabled = isAnswerSubmitting || !sessionId || !activeApiKey;
    if (question.input_kind === 'continue') {
      return (
        <div style={questionActionsStyle}>
          <button
            type="button"
            className="sidebar-item"
            disabled={disabled}
            onClick={() => submitAnswer('')}
          >
            {isAnswerSubmitting ? 'Submitting…' : 'Continue'}
          </button>
        </div>
      );
    }

    if (question.input_kind === 'boolean') {
      return (
        <div style={questionActionsStyle}>
          <button
            type="button"
            className="sidebar-item"
            disabled={disabled}
            onClick={() => submitAnswer('yes')}
          >
            Yes
          </button>
          <button
            type="button"
            className="sidebar-item"
            disabled={disabled}
            onClick={() => submitAnswer('no')}
          >
            No
          </button>
        </div>
      );
    }

    return (
      <div style={questionActionsStyle}>
        <input
          type="text"
          value={answerText}
          onChange={(event) => setAnswerText(event.target.value)}
          placeholder="Type your answer"
          style={inlineInputStyle}
          disabled={disabled}
        />
        <button
          type="button"
          className="sidebar-item"
          disabled={disabled || !answerText.trim()}
          onClick={() => submitAnswer(answerText.trim())}
        >
          {isAnswerSubmitting ? 'Submitting…' : 'Submit'}
        </button>
      </div>
    );
  };

  const renderStepInfo = (step: QuickSetStep, infoText: string): React.ReactNode => {
    if (pendingQuestion && pendingQuestion.step_name === step.name) {
      return (
        <div style={questionBlockStyle}>
          <p className="hint" style={{ marginBottom: 8 }}>
            {pendingQuestion.prompt}
          </p>
          {renderQuestionControls(pendingQuestion)}
        </div>
      );
    }
    return <span style={{ whiteSpace: 'pre-wrap' }}>{infoText || '—'}</span>;
  };

  const sessionActive = Boolean(
    session && sessionId && (session.state === 'running' || session.state === 'awaiting_input')
  );

  return (
    <section>
      <h2 className="page-title">QuickSet Runner · TV_AUTO_SYNC</h2>
      <p className="page-subtitle">
        Execute the real TV_AUTO_SYNC scenario via QuickSet. Enter tester details, STB IP, and API
        key to kick off the flow and monitor progress, steps, and logs in real time.
      </p>

      <div className="layout-two-column">
        <div className="card">
          <h3>Run TV_AUTO_SYNC</h3>
          <form onSubmit={onSubmit} className="form-grid">
            <label className="form-field">
              <span>Tester ID</span>
              <input
                type="text"
                value={form.testerId}
                onChange={handleChange('testerId')}
                style={inputStyle}
                placeholder="tester-1"
              />
            </label>
            <label className="form-field">
              <span>STB IP</span>
              <input
                type="text"
                value={form.stbIp}
                onChange={handleChange('stbIp')}
                style={inputStyle}
                placeholder="192.168.1.143"
              />
            </label>
            <label className="form-field">
              <span>API Key</span>
              <input
                type="password"
                value={form.apiKey}
                onChange={handleChange('apiKey')}
                style={inputStyle}
                placeholder="X-QuickSet-Api-Key"
              />
            </label>

            <div className="form-actions">
              <button type="submit" className="primary-btn" disabled={isSubmitting}>
                {isSubmitting ? 'Running…' : 'Run TV_AUTO_SYNC'}
              </button>
            </div>
          </form>
          {submitError && <p className="error-text">Error: {submitError}</p>}
          {pollError && <p className="error-text">Live update error: {pollError}</p>}
        </div>

        <div className="card">
          <h3>Session Status</h3>
          <dl className="session-meta">
            <div>
              <dt>Session ID</dt>
              <dd>{session?.session_id || sessionId || '—'}</dd>
            </div>
            <div>
              <dt>Tester</dt>
              <dd>{session?.tester_id || form.testerId || '—'}</dd>
            </div>
            <div>
              <dt>STB IP</dt>
              <dd>{session?.stb_ip || form.stbIp || '—'}</dd>
            </div>
            <div>
              <dt>Scenario</dt>
              <dd>{session?.scenario_name || scenarioName}</dd>
            </div>
            <div>
              <dt>Result</dt>
              <dd>
                <span className={getStatusClass(resultLabel)}>{resultLabel}</span>
              </dd>
            </div>
            <div>
              <dt>Started</dt>
              <dd>{formatDateTime(session?.start_time)}</dd>
            </div>
            <div>
              <dt>Finished</dt>
              <dd>{formatDateTime(session?.end_time)}</dd>
            </div>
          </dl>

          {session?.infra_checks && session.infra_checks.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <h4>Infra Checks</h4>
              <ul className="infra-list">
                {session.infra_checks.map((check) => (
                  <li key={check.name}>
                    <span>{check.name}</span>
                    <span className={getInfraStatusClass(check.status)}>{check.status}</span>
                    {check.message && <span className="hint"> · {check.message}</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {answerError && <p className="error-text">Answer error: {answerError}</p>}

          {pendingQuestion && (
            <div style={{ marginTop: 16 }}>
              <h4>Pending Tester Input</h4>
              <p className="hint" style={{ marginBottom: 8 }}>
                {pendingQuestion.prompt}
              </p>
              {renderQuestionControls(pendingQuestion)}
            </div>
          )}
        </div>
      </div>

      <div className="card" style={{ marginTop: 24, marginBottom: 24 }}>
        <h3>Steps Timeline</h3>
        {!timelineRows.length ? (
          <p className="hint">No steps yet. Start a session to see progress here.</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="steps-table">
              <thead>
                <tr>
                  <th style={{ minWidth: 200 }}>Step</th>
                  <th style={{ minWidth: 120 }}>Status</th>
                  <th style={{ minWidth: 200 }}>Timestamp</th>
                  <th style={{ minWidth: 360 }}>Info</th>
                </tr>
              </thead>
              <tbody>
                {timelineRows.map((row) => (
                  <tr
                    key={`${row.step.name}-${row.step.timestamp || ''}-${row.status}`}
                    className={`steps-row steps-row--${row.status.toLowerCase().replace(/\s+/g, '-')}`}
                  >
                    <td>{row.step.name}</td>
                    <td>
                      <span className={getStatusClass(row.status)}>{row.status}</span>
                    </td>
                    <td>{formatDateTime(row.step.timestamp)}</td>
                    <td>{renderStepInfo(row.step, row.infoText)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="card" style={{ marginBottom: 24 }}>
        <h3>ADB Logs</h3>
        <pre className="log-block log-panel-content">{formatLogPreview(session?.logs?.adb)}</pre>
      </div>

      <div className="card">
        <h3>Logcat Logs</h3>
        <pre className="log-block log-panel-content">{formatLogPreview(session?.logs?.logcat)}</pre>
      </div>
    </section>
  );
};

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '6px 10px',
  borderRadius: 8,
  border: '1px solid rgba(255,255,255,0.18)',
  background: 'transparent',
  color: 'inherit',
  fontSize: 13,
  marginTop: 4
};

const questionActionsStyle: React.CSSProperties = {
  display: 'flex',
  gap: 8,
  alignItems: 'center',
  flexWrap: 'wrap'
};

const inlineInputStyle: React.CSSProperties = {
  ...inputStyle,
  marginTop: 0,
  flex: 1,
  minWidth: 160
};

const questionBlockStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 8
};

export default QuickSetRunner;
