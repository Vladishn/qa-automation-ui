import React, { useState } from 'react';
import { deriveUiStatusFromAnalyzer } from '../logic/quicksetStatus';
import type { MetricStatusesResult } from '../logic/quicksetMetrics';
import type {
  TvAutoSyncSession,
  TvAutoSyncTimelineEvent,
  QuicksetAnalysisDetails,
  FailureInsight
} from '../types/quickset';
import './QuicksetSessionSummary.css';

interface Props {
  session: TvAutoSyncSession;
  timeline: TvAutoSyncTimelineEvent[];
  metricStatuses?: MetricStatusesResult | null;
}

type StatusBadge = 'PASS' | 'FAIL' | 'AWAITING_INPUT' | 'INFO';
const statusClass = (status: StatusBadge): string => {
  switch (status) {
    case 'PASS':
      return 'status-pill status-pill--pass';
    case 'FAIL':
      return 'status-pill status-pill--fail';
    case 'AWAITING_INPUT':
      return 'status-pill status-pill--running';
    default:
      return 'status-pill status-pill--info';
  }
};

const confidenceBadgeClass = (confidence: 'low' | 'medium' | 'high'): string => {
  if (confidence === 'high') {
    return 'status-pill status-pill--pass';
  }
  if (confidence === 'medium') {
    return 'status-pill status-pill--info';
  }
  return 'status-pill status-pill--fail';
};

const timelineStepByName = (timeline: TvAutoSyncTimelineEvent[], name: string) =>
  timeline.find((row) => row.name === name);

const formatAnswerLabel = (row?: TvAutoSyncTimelineEvent | null): string => {
  if (!row) {
    return 'UNKNOWN';
  }
  const answer = row.user_answer ?? (row.details?.answer as string | undefined);
  if (!answer) {
    return 'UNKNOWN';
  }
  return answer.toUpperCase();
};

const telemetryEvidenceKeys: string[] = [
  'tv_volume_events',
  'tv_osd_events',
  'volume_probe_state',
  'volume_probe_confidence',
  'volume_probe_detection_state',
  'issue_confirmed_by_probe'
];

const QuicksetSessionSummary: React.FC<Props> = ({ session, timeline }) => {
  const [showRootCause, setShowRootCause] = useState(false);
  const scenarioTitle = session.scenario_name && session.scenario_name !== 'UNKNOWN'
    ? session.scenario_name
    : 'TV_AUTO_SYNC';

  const analyzerUi = deriveUiStatusFromAnalyzer(session);
  const badgeStatus: StatusBadge =
    analyzerUi.status === 'pass' ? 'PASS' : analyzerUi.status === 'fail' ? 'FAIL' : 'AWAITING_INPUT';
  const badgeLabel = analyzerUi.label;

  const analysisSummaryRow = timelineStepByName(timeline, 'analysis_summary');
  const analysisDetails: QuicksetAnalysisDetails | undefined = analysisSummaryRow
    ? (analysisSummaryRow.details as QuicksetAnalysisDetails)
    : undefined;
  const volumeStep = timelineStepByName(timeline, 'question_tv_volume_changed');
  const osdStep = timelineStepByName(timeline, 'question_tv_osd_seen');
  const pairingStep = timelineStepByName(timeline, 'question_pairing_screen_seen');
  const brandStep = timelineStepByName(timeline, 'question_tv_brand_ui');

  const failureInsights: FailureInsight[] = analysisDetails?.failure_insights ?? [];
  const analysisEvidence = analysisDetails?.evidence as Record<string, unknown> | undefined;
  const recommendations = analysisDetails?.recommendations ?? [];
  const legacyConfidence = (analysisDetails as { confidence_level?: 'low' | 'medium' | 'high' } | undefined)
    ?.confidence_level;
  const confidence = analysisDetails?.confidence ?? legacyConfidence;
  const hasInsights = failureInsights.length > 0;
  const hasEvidence = Boolean(analysisEvidence && Object.keys(analysisEvidence).length);
  const hasRecommendations = recommendations.length > 0;
  const shouldRenderDiagnostics = hasInsights || hasEvidence || hasRecommendations || Boolean(confidence);

  const testerSignals = [
    { label: 'Volume changed', value: formatAnswerLabel(volumeStep) },
    { label: 'TV OSD seen', value: formatAnswerLabel(osdStep) },
    { label: 'Pairing screen', value: formatAnswerLabel(pairingStep) },
    { label: 'Brand (UI)', value: formatAnswerLabel(brandStep) }
  ];

  const testerVerdict = (analysisDetails?.tester_verdict as string | undefined) ?? 'UNKNOWN';
  const logVerdict = (analysisDetails?.log_verdict as string | undefined) ?? 'UNKNOWN';
  const telemetryState = (analysisDetails?.telemetry_state as string | undefined) ?? 'UNKNOWN';
  const logFailureReason =
    typeof analysisDetails?.log_failure_reason === 'string' && analysisDetails.log_failure_reason.length
      ? analysisDetails.log_failure_reason
      : null;
  const autosyncStarted = analysisDetails?.autosync_started;
  const autosyncSuccess = analysisDetails?.autosync_success;
  const conflictDetected = Boolean(analysisDetails?.conflict_tester_vs_logs);
  const telemetryWarning = !conflictDetected && logVerdict === 'INCONCLUSIVE';
  const conflictDetails =
    logFailureReason || analysisDetails?.analysis || session.analysis_text || 'Logs contradict tester answers.';
  const evidenceHighlights = telemetryEvidenceKeys
    .map((key) => ({
      key,
      value: analysisEvidence ? analysisEvidence[key] : undefined
    }))
    .filter((item) => item.value !== undefined);

  return (
    <div className="qs-summary flex flex-col gap-4 text-sm text-slate-100">
      <div className="qs-summary-header">
        <div>
          <div className="qs-summary-title">{scenarioTitle}</div>
          <div className="qs-summary-subtitle">Session {session.session_id}</div>
        </div>
        <span className={statusClass(badgeStatus)}>{badgeLabel}</span>
      </div>

      <div className="qs-summary-analysis">
        {analyzerUi.reasonLines.length
          ? analyzerUi.reasonLines.map((line, idx) => <div key={line + idx}>• {line}</div>)
          : 'Analyzer output not available yet.'}
      </div>

      <div className="qs-summary-sections">
        <section className="qs-summary-section">
          <h4 className="metric-label">TESTER SIGNALS</h4>
          <div className="qs-summary-dl">
            <div>
              <span className="qs-summary-dt">Overall tester verdict</span>
              <span className="qs-summary-dd">{testerVerdict}</span>
            </div>
            {testerSignals.map((signal) => (
              <div key={signal.label}>
                <span className="qs-summary-dt">{signal.label}</span>
                <span className="qs-summary-dd">{signal.value}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="qs-summary-section">
          <h4 className="metric-label">LOGS & TELEMETRY</h4>
          <div className="qs-summary-dl">
            <div>
              <span className="qs-summary-dt">Log verdict</span>
              <span className="qs-summary-dd">{logVerdict}</span>
            </div>
            <div>
              <span className="qs-summary-dt">Telemetry state</span>
              <span className="qs-summary-dd">{telemetryState}</span>
            </div>
            {autosyncStarted !== undefined && (
              <div>
                <span className="qs-summary-dt">Auto-sync started</span>
                <span className="qs-summary-dd">{String(autosyncStarted)}</span>
              </div>
            )}
            {autosyncSuccess !== undefined && (
              <div>
                <span className="qs-summary-dt">Auto-sync success</span>
                <span className="qs-summary-dd">{String(autosyncSuccess)}</span>
              </div>
            )}
            {logFailureReason && (
              <div>
                <span className="qs-summary-dt">Log note</span>
                <span className="qs-summary-dd">{logFailureReason}</span>
              </div>
            )}
            {evidenceHighlights.length > 0 && (
              <div>
                <span className="qs-summary-dt">Evidence</span>
                <span className="qs-summary-dd">
                  <ul className="qs-summary-evidence">
                    {evidenceHighlights.map((item) => (
                      <li key={item.key}>
                        <strong>{item.key}:</strong> {String(item.value)}
                      </li>
                    ))}
                  </ul>
                </span>
              </div>
            )}
          </div>
          {conflictDetected && (
            <div className="qs-summary-conflict">
              <strong>Conflict detected: Tester vs logs/telemetry</strong>
              <p>{conflictDetails}</p>
            </div>
          )}
          {telemetryWarning && (
            <div className="qs-summary-warning">
              Logs/telemetry inconclusive; relying on tester answers for overall verdict.
            </div>
          )}
        </section>
      </div>

      {shouldRenderDiagnostics && (
        <div className="qs-summary-diagnostics">
          {hasInsights && (
            <section className="qs-diagnostic-section">
              <button
                type="button"
                className="flex w-full items-center justify-between py-2 text-sm font-medium text-slate-200 hover:text-slate-100"
                onClick={() => setShowRootCause((value) => !value)}
              >
                <span>Why did it fail?</span>
                <svg
                  className={`h-4 w-4 transition-transform ${showRootCause ? 'rotate-180' : ''}`}
                  viewBox="0 0 20 20"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                  aria-hidden="true"
                >
                  <path
                    d="M6 8l4 4 4-4"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>
              {showRootCause && (
                <ul className="mt-1 space-y-2 text-xs text-slate-300">
                  {failureInsights.map((insight) => (
                    <li key={insight.code}>
                      <strong>{insight.title}</strong>
                      <div>{insight.description}</div>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}

          {hasEvidence && analysisEvidence && (
            <section className="qs-diagnostic-section">
              <details>
                <summary>Evidence</summary>
                <table className="qs-evidence-table">
                  <tbody>
                    {Object.entries(analysisEvidence).map(([key, value]) => (
                      <tr key={key}>
                        <th>{key}</th>
                        <td>{typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </details>
            </section>
          )}

          {hasRecommendations && (
            <section className="qs-diagnostic-section">
              <h4>Recommended next steps</h4>
              <ul>
                {recommendations.map((rec) => (
                  <li key={rec}>{rec}</li>
                ))}
              </ul>
            </section>
          )}

          {confidence && (
            <section className="qs-diagnostic-section">
              <h4>Analyzer confidence</h4>
              <span className={confidenceBadgeClass(confidence)}>{confidence.toUpperCase()}</span>
            </section>
          )}
        </div>
      )}
    </div>
  );
};

export default QuicksetSessionSummary;
