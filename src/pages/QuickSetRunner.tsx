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

const getResultFromMetadata = (step: QuickSetStep): 'PASS' | 'FAIL' | null => {
  const metadata = (step.metadata ?? {}) as Record<string, unknown>;
  const candidates: unknown[] = [
    metadata.result,
    metadata.analysis_result,
    metadata.outcome,
    metadata.verdict
  ];

  for (const value of candidates) {
    if (typeof value !== 'string') continue;
    const normalized = value.trim().toLowerCase();
    if (!normalized) continue;

    if (['pass', 'ok', 'success', 'successful'].includes(normalized)) {
      return 'PASS';
    }
    if (['fail', 'failed', 'error'].includes(normalized)) {
      return 'FAIL';
    }
  }

  return null;
};

const extractQuestionId = (step: QuickSetStep): string | undefined => {
  const metadata = (step.metadata ?? {}) as Record<string, unknown>;
  if (typeof metadata.question_id === 'string' && metadata.question_id.trim()) {
    return metadata.question_id.trim().toLowerCase();
  }
  const match = step.name?.match(/^question_(.+?)(?:_answer)?$/i);
  return match ? match[1].toLowerCase() : undefined;
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
  return metaStatus === 'fail' || metaStatus === 'error' || metaResult === 'fail' || metaResult === 'error';
};

const shouldDisplayStep = (step: QuickSetStep): boolean => {
  const name = step.name || '';
  if (!name) return false;
  if (name === 'log_analysis_complete' || name === 'tester_questions') {
    return false;
  }

  const metadata = (step.metadata ?? {}) as Record<string, unknown>;
  if (metadata.tester_visible === false) {
    return false;
  }

  const questionId = extractQuestionId(step);
  if (name.endsWith('_answer')) {
    return false;
  }
  if (questionId === 'volume_probe') {
    return false;
  }

  if (name.startsWith('question_')) {
    return true;
  }

  if (name === 'analysis_summary') {
    return true;
  }

  if (name.startsWith('adb_') || name.startsWith('logcat_')) {
    return shouldDisplayInfraStep(step);
  }

  const statusLower = (step.status || '').toLowerCase();
  if (statusLower === 'info') {
    return Boolean(getStepInfo(step));
  }

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
    case 'manual_trigger':
    case 'notes':
      return hasAnswer || sessionEnded ? 'INFO' : 'AWAITING INPUT';
    case 'tv_volume_changed':
      if (!hasAnswer) {
        return sessionEnded ? 'INFO' : 'AWAITING INPUT';
      }
      return isYes(answerValue) ? 'PASS' : 'FAIL';
    case 'tv_osd_seen': {
      const probeAnswer = getAnswerValue(answerMap.get('volume_probe'));
      const hasProbe = Boolean(probeAnswer.trim());
      if (!hasAnswer || !hasProbe) {
        return sessionEnded ? 'FAIL' : 'AWAITING INPUT';
      }
      return isYes(answerValue) && isYes(probeAnswer) ? 'PASS' : 'FAIL';
    }
    case 'pairing_screen_seen':
      if (!hasAnswer) {
        return sessionEnded ? 'FAIL' : 'AWAITING INPUT';
      }
      return isYes(answerValue) ? 'PASS' : 'FAIL';
    case 'tv_brand_ui':
      if (!hasAnswer) {
        return sessionEnded ? 'FAIL' : 'AWAITING INPUT';
      }
      return answerValue.trim().length > 0 ? 'PASS' : 'FAIL';
    default:
      if (!hasAnswer) {
        return sessionEnded ? 'INFO' : 'AWAITING INPUT';
      }
      return 'INFO';
  }
};

const getDisplayStatus = (
  step: QuickSetStep,
  session: QuickSetSession | null,
  answerMap: AnswerMap
): string => {
  const questionId = extractQuestionId(step);
  if (questionId) {
    return getQuestionStatus(questionId, session, answerMap);
  }

  if (step.name === 'analysis_summary') {
    const sessionResult = (session?.result || '').toLowerCase();
    if (sessionResult === 'pass' || sessionResult === 'fail') {
      return sessionResult.toUpperCase();
    }
  }

  const metadataResult = getResultFromMetadata(step);
  if (metadataResult) {
    return metadataResult;
  }

  const raw = (step.status || '').toLowerCase();
  const hasEnded = Boolean(session?.end_time);

  if (!hasEnded) {
    if (!raw) {
      return 'RUNNING';
    }
    if (raw === 'pending') {
      return 'AWAITING INPUT';
    }
    if (raw === 'info' || raw === 'running') {
      return 'RUNNING';
    }
    return raw.toUpperCase();
  }

  if (raw === 'pass' || raw === 'fail') {
    return raw.toUpperCase();
  }

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

  const handleChange = (field: keyof typeof form) => (event: React.ChangeEvent<HTMLInputElement>) => {
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
          <button type="button" className="sidebar-item" disabled={disabled} onClick={() => submitAnswer('')}>
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
        Execute the real TV_AUTO_SYNC scenario via QuickSet. Enter tester details, STB IP, and API key
        to kick off the flow and monitor progress, steps, and logs in real time.
      </p>

      {submitError && (
        <p className="hint" style={{ color: '#e67e22' }}>
          {submitError}
        </p>
      )}
      {pollError && (
        <p className="hint" style={{ color: '#e67e22' }}>
          {pollError}
        </p>
      )}
      {answerError && (
        <p className="hint" style={{ color: '#e67e22' }}>
          {answerError}
        </p>
      )}

      <div className="card" style={{ marginBottom: 24 }}>
        <h3>Run TV_AUTO_SYNC</h3>
        <form onSubmit={onSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <label>
            Tester ID
            <input
              type="text"
              value={form.testerId}
              onChange={handleChange('testerId')}
              placeholder="tester-golan-001"
              style={inputStyle}
            />
          </label>
          <label>
            STB IP
            <input
              type="text"
              value={form.stbIp}
              onChange={handleChange('stbIp')}
              placeholder="192.168.1.200"
              style={inputStyle}
            />
          </label>
          <label>
            API Key
            <input
              type="password"
              value={form.apiKey}
              onChange={handleChange('apiKey')}
              placeholder="X-QuickSet-Api-Key"
              style={inputStyle}
            />
          </label>
          <label>
            Scenario
            <input type="text" value={scenarioName} disabled style={inputStyle} />
          </label>
          <button type="submit" className="sidebar-item" disabled={isSubmitting || sessionActive}>
            {isSubmitting ? 'Running…' : sessionActive ? 'Scenario Active' : 'Run TV_AUTO_SYNC'}
          </button>
        </form>
      </div>

      <div className="card" style={{ marginBottom: 24 }}>
        <h3>Session Status</h3>
        {sessionId ? (
          <div>
            <p className="hint">Session ID: {sessionId}</p>
            <p className="hint">Scenario: {scenarioName}</p>
            <p className="hint">
              Result: <span className={getStatusClass(resultLabel)}>{resultLabel}</span>
            </p>
            <div className="summary-block">
              <div className="summary-block-label">Summary</div>
              <div className="summary-block-text">{session?.summary || '—'}</div>
            </div>
            <p className="hint">TV Model: {session?.tv_model || '—'}</p>
            <p className="hint">Started: {formatDateTime(session?.start_time)}</p>
            <p className="hint">Finished: {formatDateTime(session?.end_time)}</p>
          </div>
        ) : (
          <p className="hint">No run started yet.</p>
        )}
      </div>

      {session?.infra_checks && session.infra_checks.length > 0 && (
        <div className="card" style={{ marginBottom: 24 }}>
          <h3>Infra Checks</h3>
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Status</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {session.infra_checks.map((check) => (
                <tr key={check.name}>
                  <td>{check.name}</td>
                  <td>
                    <span className={getInfraStatusClass(check.status)}>{check.status.toUpperCase()}</span>
                  </td>
                  <td>{check.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="card" style={{ marginBottom: 24 }}>
        <h3>Steps Timeline</h3>
        {timelineRows.length === 0 ? (
          <p className="hint">Steps will appear once the run starts.</p>
        ) : (
          <div style={{ width: '100%', overflowX: 'auto' }}>
            <table className="table" style={{ tableLayout: 'fixed', minWidth: 640 }}>
              <thead>
                <tr>
                  <th>Step</th>
                  <th>Status</th>
                  <th>Timestamp</th>
                  <th>Info</th>
                </tr>
              </thead>
              <tbody>
                {timelineRows.map((row) => (
                  <tr key={`${row.step.name}-${row.step.timestamp ?? ''}-${row.status}`}>
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
