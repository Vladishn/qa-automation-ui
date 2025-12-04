import React, { useEffect, useMemo, useState } from 'react';
import StepsTimeline from '../components/StepsTimeline';
import QuicksetSessionSummary from '../components/QuicksetSessionSummary';
import type { QuickSetQuestion, QuickSetSession, SessionSummary, TimelineRow } from '../types/domain';
import { runScenario, getSession, answerQuestion, fetchSessionTimeline } from '../services/quicksetService';

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

const getStatusClass = (label: string): string => {
  const normalized = label.toUpperCase();
  if (normalized === 'PASS') return 'status-pill status-pill--pass';
  if (normalized === 'FAIL') return 'status-pill status-pill--fail';
  if (normalized === 'RUNNING') return 'status-pill status-pill--running';
  if (normalized === 'AWAITING INPUT') return 'status-pill status-pill--running';
  if (normalized === 'AWAITING_INPUT') return 'status-pill status-pill--running';
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
  const [sessionSummary, setSessionSummary] = useState<SessionSummary | null>(null);
  const [timeline, setTimeline] = useState<TimelineRow[]>([]);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [timelineError, setTimelineError] = useState<string | null>(null);

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

  useEffect(() => {
    if (!sessionId) {
      setSessionSummary(null);
      setTimeline([]);
      setTimelineError(null);
      setTimelineLoading(false);
      return () => {};
    }

    setSessionSummary(null);
    setTimeline([]);
    setTimelineError(null);
    const currentSessionId = sessionId;

    let cancelled = false;
    let pollId: number | null = null;

    const load = async (showSpinner: boolean) => {
      if (showSpinner) {
        setTimelineLoading(true);
      }
      try {
        const data = await fetchSessionTimeline(currentSessionId);
        if (!cancelled) {
          setSessionSummary(data.session);
          setTimeline(data.timeline ?? []);
          setTimelineError(null);
          const finished = data.session.overall_status !== 'AWAITING_INPUT' && (data.timeline?.length ?? 0) > 0;
          if (finished && pollId !== null) {
            window.clearInterval(pollId);
            pollId = null;
          }
        }
      } catch (err) {
        if (!cancelled) {
          setTimelineError(err instanceof Error ? err.message : 'Failed to load timeline');
        }
      } finally {
        if (!cancelled && showSpinner) {
          setTimelineLoading(false);
        }
      }
    };

    load(true);
    pollId = window.setInterval(() => {
      void load(false);
    }, 2000);

    return () => {
      cancelled = true;
      if (pollId !== null) {
        window.clearInterval(pollId);
      }
    };
  }, [sessionId]);

  const resultLabel = useMemo(() => {
    if (sessionSummary) {
      return sessionSummary.overall_status === 'AWAITING_INPUT'
        ? 'AWAITING INPUT'
        : sessionSummary.overall_status;
    }
    return 'Not started';
  }, [sessionSummary]);

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

  const sessionActive = Boolean(
    session && sessionId && (session.state === 'running' || session.state === 'awaiting_input')
  );

  const showLogs = sessionSummary?.has_failure === true;
  const timelineForDisplay = sessionSummary ? timeline : null;
  const startedAt = formatDateTime(sessionSummary?.started_at);
  const finishedAt = formatDateTime(sessionSummary?.finished_at);

  const renderQuicksetSummary = () => {
    if (!sessionId) {
      return <p className="hint">Run a session to see the QuickSet analysis summary.</p>;
    }
    if (timelineError) {
      return (
        <p className="hint" style={{ color: '#ff8a8a' }}>
          Failed to load summary: {timelineError}
        </p>
      );
    }
    if (timelineLoading && !sessionSummary) {
      return <p className="hint">Loading analysis summary…</p>;
    }
    if (!sessionSummary) {
      return <p className="hint">No analysis summary yet.</p>;
    }
    return <QuicksetSessionSummary session={sessionSummary} timeline={timeline} />;
  };

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
            <dd>{startedAt}</dd>
          </div>
          <div>
            <dt>Finished</dt>
            <dd>{finishedAt}</dd>
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

      <div className="card" style={{ marginBottom: 24 }}>
        <h3>QuickSet Summary</h3>
        {renderQuicksetSummary()}
      </div>

      <div className="card" style={{ marginBottom: 24 }}>
        <h3>Steps Timeline</h3>
        <StepsTimeline
          sessionId={sessionId}
          rows={timelineForDisplay}
          isLoading={timelineLoading}
          error={timelineError}
        />
      </div>

      {showLogs && (
        <>
          <div className="card" style={{ marginBottom: 24 }}>
            <h3>ADB Logs</h3>
            <div className="adb-logs-container">
              <pre className="adb-logs-text">{formatLogPreview(session?.logs?.adb)}</pre>
            </div>
          </div>

          <div className="card">
            <h3>Logcat Logs</h3>
            <div className="adb-logs-container">
              <pre className="adb-logs-text">{formatLogPreview(session?.logs?.logcat)}</pre>
            </div>
          </div>
        </>
      )}
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

export default QuickSetRunner;
