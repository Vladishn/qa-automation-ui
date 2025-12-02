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

const getDisplayStatus = (step: QuickSetStep, session: QuickSetSession | null): string => {
  const raw = (step.status || '').toLowerCase();
  const hasEnded = Boolean(session?.end_time);
  const sessionResult = (session?.result || '').toLowerCase();

  if (step.name === 'analysis_summary' && (sessionResult === 'pass' || sessionResult === 'fail')) {
    return sessionResult.toUpperCase();
  }

  if (!hasEnded) {
    return raw ? raw.toUpperCase() : 'RUNNING';
  }

  if (raw === 'pass' || raw === 'fail') {
    return raw.toUpperCase();
  }

  if (raw === 'running' || raw === 'info') {
    return 'INFO';
  }

  return raw ? raw.toUpperCase() : 'INFO';
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

  const shouldDisplayStep = (step: QuickSetStep): boolean => {
    const metadata = (step.metadata ?? {}) as Record<string, any>;
    if (metadata?.tester_visible === false) {
      return false;
    }
    if (step.status === 'INFO') {
      if (metadata?.prompt || metadata?.analysis || metadata?.message) {
        return true;
      }
      if (step.name.startsWith('question_')) {
        return true;
      }
      return false;
    }
    return true;
  };

  const visibleSteps = steps.filter(shouldDisplayStep);

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

  const renderStepInfo = (step: QuickSetStep): React.ReactNode => {
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
    return getStepInfo(step) || '—';
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
        <form
          onSubmit={onSubmit}
          style={{ display: 'flex', flexDirection: 'column', gap: 12 }}
        >
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
              Result:{' '}
              <span className={getStatusClass(resultLabel)}>
                {resultLabel}
              </span>
            </p>
            <div className="hint" style={{ fontWeight: 600, marginTop: 8 }}>Summary</div>
            <div className="hint" style={{ whiteSpace: 'pre-wrap' }}>{session?.summary || '—'}</div>
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
        {visibleSteps.length === 0 ? (
          <p className="hint">Steps will appear once the run starts.</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Step</th>
                <th>Status</th>
                <th>Timestamp</th>
                <th>Info</th>
              </tr>
            </thead>
            <tbody>
              {visibleSteps.map((step) => {
                const displayStatus = getDisplayStatus(step, session);
                return (
                  <tr key={`${step.name}-${step.timestamp ?? ''}`}>
                    <td>{step.name}</td>
                    <td>
                      <span className={getStatusClass(displayStatus)}>{displayStatus}</span>
                    </td>
                    <td>{formatDateTime(step.timestamp)}</td>
                    <td>{renderStepInfo(step)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
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
