import React, { useEffect, useMemo, useState } from 'react';
import StepsTimeline from '../components/StepsTimeline';
import QuicksetSessionSummary from '../components/QuicksetSessionSummary';
import { DashboardCard } from '../components/layout/DashboardCard';
import { StbIpField } from '../components/fields/StbIpField';
import type { QuickSetQuestion } from '../types/domain';
import type {
  AnalyzerStepStatus,
  MetricTriState,
  QuicksetAnalysisDetails,
  TvAutoSyncTimelineEvent,
  TvAutoSyncSession
} from '../types/quickset';
import { deriveUiStatusFromAnalyzer } from '../logic/quicksetStatus';
import { deriveMetricStatuses, type MetricStatusesResult } from '../logic/quicksetMetrics';
import { runScenario, answerQuestion, type QuicksetScenarioId } from '../services/quicksetService';
import { useSessionPolling } from '../hooks/useSessionPolling';


const defaultForm = {
  testerId: '',
  stbIp: '',
  apiKey: '',
  expectedChannel: '3'
};

const RCU_SCENARIOS: ReadonlyArray<{ id: QuicksetScenarioId; label: string }> = [
  { id: 'TV_AUTO_SYNC', label: 'TV Auto Sync' },
  { id: 'LIVE_BUTTON_MAPPING', label: 'Live Button Mapping' }
];
type TimelineRowWithStatus = TvAutoSyncTimelineEvent & { statusDisplay?: AnalyzerStepStatus | MetricTriState };
const INITIAL_SESSION_HISTORY: Record<QuicksetScenarioId, string | null> = {
  TV_AUTO_SYNC: null,
  LIVE_BUTTON_MAPPING: null
};
const isFinalAnalyzerStatus = (value?: string | null): boolean => {
  if (!value) {
    return false;
  }
  const normalized = value.toUpperCase();
  return normalized === 'PASS' || normalized === 'FAIL' || normalized === 'INCONCLUSIVE';
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
  if (normalized === 'PENDING') return 'status-pill status-pill--running';
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

const pickTriState = (value: unknown): MetricTriState | undefined => {
  if (value === 'OK' || value === 'FAIL' || value === 'INCOMPATIBILITY' || value === 'NOT_EVALUATED') {
    return value;
  }
  return undefined;
};

const QuickSetRunner: React.FC = () => {
  const [form, setForm] = useState(defaultForm);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [lastSessionByScenario, setLastSessionByScenario] =
    useState<Record<QuicksetScenarioId, string | null>>(() => ({ ...INITIAL_SESSION_HISTORY }));
  const [activeApiKey, setActiveApiKey] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [answerError, setAnswerError] = useState<string | null>(null);
  const [answerText, setAnswerText] = useState('');
  const [isAnswerSubmitting, setIsAnswerSubmitting] = useState(false);
  const [selectedScenarioId, setSelectedScenarioId] = useState<QuicksetScenarioId>('TV_AUTO_SYNC');
  const [completionBanner, setCompletionBanner] = useState<{ sessionId: string; timestamp: number } | null>(null);

  const { data: sessionData, error: pollError, setData: setSessionEnvelope } =
    useSessionPolling(selectedSessionId, activeApiKey);

  const analyzerSession = sessionData?.session ?? null;
  const runtimeSession = sessionData?.quickset_session ?? null;
  const timeline = (sessionData?.timeline ?? []) as TvAutoSyncTimelineEvent[];
  const pendingQuestion = runtimeSession?.pending_question ?? null;
  const analyzerFinished = Boolean(
    analyzerSession &&
      (analyzerSession.finished_at || isFinalAnalyzerStatus(analyzerSession.overall_status))
  );

  useEffect(() => {
    if (!selectedSessionId) {
      setCompletionBanner(null);
      return;
    }
    if (analyzerFinished) {
      setCompletionBanner((prev) =>
        prev?.sessionId === selectedSessionId ? prev : { sessionId: selectedSessionId, timestamp: Date.now() }
      );
    } else if (completionBanner?.sessionId === selectedSessionId) {
      setCompletionBanner(null);
    }
  }, [selectedSessionId, analyzerFinished, completionBanner?.sessionId]);

  const handleChange =
    (field: keyof typeof form) =>
    (event: React.ChangeEvent<HTMLInputElement>) => {
      setForm((prev) => ({ ...prev, [field]: event.target.value }));
    };

  const currentScenarioLabel = useMemo(() => {
    return RCU_SCENARIOS.find((scenario) => scenario.id === selectedScenarioId)?.label ?? 'TV Auto Sync';
  }, [selectedScenarioId]);

  const handleStartScenario = async () => {
    setSubmitError(null);

    const trimmedTester = form.testerId.trim();
    const trimmedIp = form.stbIp.trim();
    const trimmedKey = form.apiKey.trim();
    if (!trimmedTester || !trimmedIp || !trimmedKey) {
      setSubmitError('Tester ID, STB IP, and API key are required.');
      return;
    }

    let expectedChannelValue: number | undefined;
    if (selectedScenarioId === 'LIVE_BUTTON_MAPPING') {
      const parsed = Number(form.expectedChannel);
      if (!Number.isInteger(parsed) || parsed < 1 || parsed > 9999) {
        setSubmitError('Expected channel must be an integer between 1 and 9999.');
        return;
      }
      expectedChannelValue = parsed;
    }

    try {
      setIsSubmitting(true);
      const response = await runScenario({
        testerId: trimmedTester,
        stbIp: trimmedIp,
        apiKey: trimmedKey,
        scenarioName: selectedScenarioId,
        expectedChannel: expectedChannelValue
      });
      setLastSessionByScenario((prev) => ({
        ...prev,
        [selectedScenarioId]: response.session_id
      }));
      setSelectedSessionId(response.session_id);
      setActiveApiKey(trimmedKey);
      setSessionEnvelope(null);
      setAnswerText('');
      setCompletionBanner(null);
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : 'Failed to run scenario');
    } finally {
      setIsSubmitting(false);
    }
  };

  useEffect(() => {
    setAnswerText('');
  }, [pendingQuestion?.id]);

  const analyzerUi = useMemo(
    () => (analyzerSession ? deriveUiStatusFromAnalyzer(analyzerSession) : null),
    [analyzerSession]
  );

  const resultLabel = analyzerUi?.label ?? 'Not started';
  const analysisSummaryRow = useMemo(
    () => timeline.find((row) => row.name === 'analysis_summary'),
    [timeline]
  );
  const analysisDetails = useMemo(
    () => (analysisSummaryRow ? (analysisSummaryRow.details as QuicksetAnalysisDetails) : undefined),
    [analysisSummaryRow]
  );
  const metricStatuses = useMemo<MetricStatusesResult | null>(() => {
    if (!analyzerSession) {
      return null;
    }
    const derived = deriveMetricStatuses(analyzerSession, analysisDetails);
    return {
      ...derived,
      brandStatus: pickTriState(analyzerSession.brand_status) ?? derived.brandStatus,
      volumeStatus: pickTriState(analyzerSession.volume_status) ?? derived.volumeStatus,
      osdStatus: pickTriState(analyzerSession.osd_status) ?? derived.osdStatus,
      hasBrandMismatch:
        typeof analyzerSession.brand_mismatch === 'boolean'
          ? analyzerSession.brand_mismatch
          : derived.hasBrandMismatch
    };
  }, [analyzerSession, analysisDetails]);
  const timelineForDisplay: TimelineRowWithStatus[] | null = timeline ?? null;
  const handleScenarioSelect = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const nextScenario = event.target.value as QuicksetScenarioId;
    setSelectedScenarioId(nextScenario);
    const nextSession = lastSessionByScenario[nextScenario] ?? null;
    setSelectedSessionId(nextSession);
    setSessionEnvelope(null);
    setAnswerText('');
    if (nextScenario === 'LIVE_BUTTON_MAPPING' && !form.expectedChannel) {
      setForm((prev) => ({ ...prev, expectedChannel: '3' }));
    }
    if (!nextSession) {
      setCompletionBanner(null);
    }
  };

  const submitAnswer = async (value: string) => {
    if (!selectedSessionId || !activeApiKey || !pendingQuestion || isAnswerSubmitting) {
      return;
    }
    try {
      setAnswerError(null);
      setIsAnswerSubmitting(true);
      const updated = await answerQuestion(selectedSessionId, activeApiKey, value);
      setSessionEnvelope(updated);
      setAnswerText('');
    } catch (error) {
      setAnswerError(error instanceof Error ? error.message : 'Failed to send answer');
    } finally {
      setIsAnswerSubmitting(false);
    }
  };

  const renderQuestionControls = (question: QuickSetQuestion) => {
    const disabled = isAnswerSubmitting || !selectedSessionId || !activeApiKey;

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

  const sessionActive = Boolean(
    runtimeSession &&
      selectedSessionId &&
      runtimeSession.session_id === selectedSessionId &&
      (runtimeSession.state === 'running' || runtimeSession.state === 'awaiting_input')
  );

  const showLogs = analyzerSession?.has_failure === true;
  const startedAt = formatDateTime(analyzerSession?.started_at);
  const finishedAt = formatDateTime(analyzerSession?.finished_at);

  const renderQuicksetSummary = () => {
    if (!selectedSessionId) {
      return <p className="hint">Run a session to see the QuickSet analysis summary.</p>;
    }
    if (!analyzerSession) {
      return <p className="hint">Analyzer output not available yet.</p>;
    }
    return (
      <QuicksetSessionSummary
        session={analyzerSession}
        timeline={timeline}
        metricStatuses={metricStatuses}
      />
    );
  };

  return (
    <div className="mx-auto w-full max-w-[1400px] space-y-6 px-4 py-10 sm:px-6 lg:px-8">
      <div className="space-y-3">
        <h2 className="page-title">RCU Tests</h2>
        <p className="page-subtitle">
          Execute the {currentScenarioLabel} scenario via QuickSet. Enter tester details, STB IP, and API
          key to kick off the flow and monitor progress, steps, and logs in real time.
        </p>
      </div>

      <div className="space-y-2">
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
      </div>

      {/* TOP ROW: Run form + Session status */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <DashboardCard title="Run QuickSet Scenario">
          <div className="flex flex-col space-y-4">
            <label className="flex flex-col space-y-1 text-sm font-medium">
              <span>Scenario</span>
              <select
                value={selectedScenarioId}
                onChange={handleScenarioSelect}
                className="mt-0 w-full rounded-lg border border-white/20 bg-transparent p-2 text-sm"
              >
                {RCU_SCENARIOS.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="flex flex-col space-y-1 text-sm font-medium">
              <span>Tester ID</span>
              <input
                type="text"
                name="testerId"
                value={form.testerId}
                onChange={handleChange('testerId')}
                placeholder="tester-golan-001"
                autoComplete="off"
                autoCorrect="off"
                autoCapitalize="off"
                spellCheck={false}
                style={inputStyle}
              />
            </label>

            <label className="flex flex-col space-y-1 text-sm font-medium">
              <span>STB IP</span>
              <StbIpField
                value={form.stbIp}
                onChange={(val) => setForm((prev) => ({ ...prev, stbIp: val }))}
                disabled={isSubmitting || sessionActive}
              />
            </label>

            <label className="flex flex-col space-y-1 text-sm font-medium">
              <span>API Key</span>
              <input
                type="text"
                name="quicksetApiKey"
                className="[text-security:disc] [-webkit-text-security:disc]"
                value={form.apiKey}
                onChange={handleChange('apiKey')}
                placeholder="X-QuickSet-Api-Key"
                autoComplete="off"
                autoCorrect="off"
                autoCapitalize="off"
                spellCheck={false}
                style={inputStyle}
              />
            </label>

            {selectedScenarioId === 'LIVE_BUTTON_MAPPING' && (
              <label className="flex flex-col space-y-1 text-sm font-medium">
                <span>Expected channel</span>
                <input
                  type="number"
                  min={1}
                  max={9999}
                  name="expectedChannel"
                  value={form.expectedChannel}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, expectedChannel: event.target.value }))
                  }
                  placeholder="3"
                  autoComplete="off"
                  autoCorrect="off"
                  autoCapitalize="off"
                  spellCheck={false}
                  style={inputStyle}
                  disabled={isSubmitting || sessionActive}
                />
              </label>
            )}

            <button
              type="button"
              onClick={handleStartScenario}
              className="mt-4 inline-flex items-center justify-center rounded-xl bg-indigo-500 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-600 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={isSubmitting || sessionActive}
            >
              {isSubmitting ? 'Starting…' : sessionActive ? 'Scenario Active' : 'Start test'}
            </button>
          </div>
        </DashboardCard>

        <DashboardCard title="Session Status">
          <dl className="grid grid-cols-1 gap-x-8 gap-y-2 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-400">Session ID</dt>
              <dd className="text-sm font-mono text-slate-100">
                {runtimeSession?.session_id || selectedSessionId || '—'}
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-400">Tester</dt>
              <dd className="text-sm text-slate-100">
                {runtimeSession?.tester_id || form.testerId || '—'}
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-400">STB IP</dt>
              <dd className="text-sm text-slate-100">
                {runtimeSession?.stb_ip || form.stbIp || '—'}
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-400">Scenario</dt>
              <dd className="text-sm text-slate-100">
                {runtimeSession?.scenario_name || selectedScenarioId}
              </dd>
            </div>
            <div className="flex flex-col">
              <dt className="text-xs uppercase tracking-wide text-slate-400">Result</dt>
              <dd className="text-sm text-slate-100">
                <span className={getStatusClass(resultLabel)}>{resultLabel}</span>
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-400">Started</dt>
              <dd className="text-sm text-slate-100">{startedAt}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-400">Finished</dt>
              <dd className="text-sm text-slate-100">{finishedAt}</dd>
            </div>
          </dl>

          {runtimeSession?.infra_checks && runtimeSession.infra_checks.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-semibold">Infra Checks</h4>
              <ul className="infra-list space-y-1">
                {runtimeSession.infra_checks.map((check) => (
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
            <div className="space-y-2">
              <h4 className="text-sm font-semibold">Pending Tester Input</h4>
              <p className="hint">{pendingQuestion.prompt}</p>
              {renderQuestionControls(pendingQuestion)}
            </div>
          )}
        </DashboardCard>
      </div>

      {completionBanner?.sessionId === selectedSessionId && (
        <div className="rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-200">
          Test completed for session {completionBanner.sessionId}.
        </div>
      )}

      {/* SECOND ROW: Summary + Timeline */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 items-stretch">
        <DashboardCard title="QuickSet Summary" className="h-full flex flex-col" bodyClassName="flex-1 flex flex-col">
          {renderQuicksetSummary()}
        </DashboardCard>

        <DashboardCard
          title="Steps Timeline"
          className="h-full flex flex-col"
          bodyClassName="px-0 pb-0 flex-1 flex flex-col"
        >
          <StepsTimeline sessionId={selectedSessionId} rows={timelineForDisplay} />
        </DashboardCard>
      </div>

      {showLogs && (
        <div className="space-y-6">
          <DashboardCard title="ADB logs">
            <div className="adb-logs-container">
              <pre className="adb-logs-text">
                {formatLogPreview(runtimeSession?.logs?.adb)}
              </pre>
            </div>
          </DashboardCard>

          <DashboardCard title="Logcat logs">
            <div className="adb-logs-container">
              <pre className="adb-logs-text">
                {formatLogPreview(runtimeSession?.logs?.logcat)}
              </pre>
            </div>
          </DashboardCard>
        </div>
      )}
    </div>
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
