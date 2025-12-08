import React from 'react';
import { deriveUiStatusFromAnalyzer, deriveVolumeTileState, deriveOsdTileState } from '../logic/quicksetStatus';
import { deriveMetricStatuses, formatTriStateLabel } from '../logic/quicksetMetrics';
import type { MetricStatusesResult } from '../logic/quicksetMetrics';
import type {
  TvAutoSyncSession,
  TvAutoSyncTimelineEvent,
  QuicksetAnalysisDetails,
  FailureInsight,
  MetricTriState
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

type StatusVariant = 'success' | 'danger' | 'neutral' | 'warning';
interface StatusDescriptor {
  label: string;
  variant: StatusVariant;
  detail?: string;
}

const pillClassForVariant = (variant: StatusVariant): string => {
  switch (variant) {
    case 'success':
      return 'status-pill status-pill--pass';
    case 'danger':
      return 'status-pill status-pill--fail';
    case 'warning':
      return 'status-pill status-pill--info';
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

const warningPillStyle: React.CSSProperties = {
  background: 'rgba(251, 191, 36, 0.18)',
  color: '#fbbf24'
};

const describeBinaryMetricStatus = (
  status: MetricTriState,
  metric: 'volume' | 'osd',
  analyzerIssue: boolean,
  testerAnswer: string | null | undefined
): StatusDescriptor => {
  const normalizedAnswer = testerAnswer ? testerAnswer.trim().toLowerCase() : null;
  const testerSeesIssue = normalizedAnswer === 'no';
  const testerSeesOk = normalizedAnswer === 'yes';
  const pillLabel = formatTriStateLabel(status);
  const descriptions =
    metric === 'volume'
      ? {
          ok: 'Analyzer and tester agree TV volume control is OK.',
          fail: 'Analyzer confirmed volume issue.',
          incompatAnalyzerIssue: 'Tester reported control, but analyzer saw no TV volume events.',
          incompatTesterIssue: 'Tester reported no control, but analyzer saw TV volume events.',
          incompatGeneric: 'Analyzer and tester disagree on TV volume control.'
        }
      : {
          ok: 'Analyzer and tester agree TV OSD is OK.',
          fail: 'Analyzer confirmed OSD issue.',
          incompatAnalyzerIssue: 'Tester reported seeing OSD, but analyzer saw no TV OSD events.',
          incompatTesterIssue: 'Tester reported no OSD, but analyzer saw TV OSD events.',
          incompatGeneric: 'Analyzer and tester disagree on TV OSD.'
        };

  if (status === 'FAIL') {
    return { label: pillLabel, variant: 'danger', detail: descriptions.fail };
  }
  if (status === 'INCOMPATIBILITY') {
    if (analyzerIssue) {
      return {
        label: pillLabel,
        variant: 'warning',
        detail: testerSeesOk ? descriptions.incompatAnalyzerIssue : descriptions.incompatGeneric
      };
    }
    if (testerSeesIssue) {
      return {
        label: pillLabel,
        variant: 'warning',
        detail: descriptions.incompatTesterIssue
      };
    }
    return {
      label: pillLabel,
      variant: 'warning',
      detail: descriptions.incompatGeneric
    };
  }
  if (status === 'OK') {
    return { label: pillLabel, variant: 'success', detail: descriptions.ok };
  }
  return { label: pillLabel, variant: 'neutral', detail: 'Awaiting analyzer' };
};

const renderMetricPill = (descriptor: StatusDescriptor) => (
  <span
    className={pillClassForVariant(descriptor.variant)}
    style={descriptor.variant === 'warning' ? warningPillStyle : undefined}
  >
    {descriptor.label}
  </span>
);

const asTriState = (value: unknown): MetricTriState | undefined => {
  if (value === 'OK' || value === 'FAIL' || value === 'INCOMPATIBILITY' || value === 'NOT_EVALUATED') {
    return value;
  }
  return undefined;
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

const QuicksetSessionSummary: React.FC<Props> = ({ session, timeline, metricStatuses }) => {
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
  const derivedMetrics = deriveMetricStatuses(session, analysisDetails);
  const metrics: MetricStatusesResult =
    metricStatuses ??
    {
      ...derivedMetrics,
      brandStatus: asTriState(session.brand_status) ?? derivedMetrics.brandStatus,
      volumeStatus: asTriState(session.volume_status) ?? derivedMetrics.volumeStatus,
      osdStatus: asTriState(session.osd_status) ?? derivedMetrics.osdStatus,
      hasBrandMismatch:
        typeof session.brand_mismatch === 'boolean' ? session.brand_mismatch : derivedMetrics.hasBrandMismatch
    };
  const analyzerReady = metrics.analyzerReady;
  const { brandStatus: brandTriState, volumeStatus: volumeTriState, osdStatus: osdTriState } = metrics;

  const volumeStep = timelineStepByName(timeline, 'question_tv_volume_changed');
  const osdStep = timelineStepByName(timeline, 'question_tv_osd_seen');
  const pairingStep = timelineStepByName(timeline, 'question_pairing_screen_seen');
  const brandStep = timelineStepByName(timeline, 'question_tv_brand_ui');

  const volumeTile = deriveVolumeTileState(session, timeline);
  const osdTile = deriveOsdTileState(session, timeline);

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

  const brandStatus: StatusDescriptor = (() => {
    const brandLabel = formatTriStateLabel(brandTriState);
    if (brandTriState === 'FAIL') {
      // FAIL should not occur for brand, but fall back to mismatch copy.
      const mismatchDetail =
        session.tv_brand_user && session.tv_brand_log
          ? `Tester saw ${session.tv_brand_user}, logs show ${session.tv_brand_log}.`
          : 'Brand mismatch detected between UI and logs.';
      return { label: brandLabel, variant: 'danger', detail: mismatchDetail };
    }
    if (brandTriState === 'INCOMPATIBILITY') {
      return {
        label: brandLabel,
        variant: 'warning',
        detail:
          session.tv_brand_user && session.tv_brand_log
            ? `Tester saw ${session.tv_brand_user}, logs show ${session.tv_brand_log}.`
            : 'Analyzer and tester disagree on brand. Analyzer sees mismatch in logs.'
      };
    }
    if (brandTriState === 'OK') {
      return { label: brandLabel, variant: 'success', detail: 'Brand match between UI and logs.' };
    }
    return { label: brandLabel, variant: 'neutral', detail: 'Awaiting analyzer' };
  })();

  const volumeStatus = describeBinaryMetricStatus(
    volumeTriState,
    'volume',
    Boolean(session.has_volume_issue),
    volumeTile.answer
  );
  const osdStatus = describeBinaryMetricStatus(
    osdTriState,
    'osd',
    Boolean(session.has_osd_issue),
    osdTile.answer
  );

  const analysisNotes =
    (session as { analysis_result?: { notes?: string | null } }).analysis_result?.notes ?? null;
  const testerNotesRaw = session.notes ?? analysisNotes ?? null;
  const hasTesterNotes = typeof testerNotesRaw === 'string' && testerNotesRaw.trim().length > 0;
  const testerNotes = hasTesterNotes ? testerNotesRaw.trim() : null;

  return (
    <div className="qs-summary">
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

      <div className="qs-summary-grid">
        <div>
          <div className="metric-label">BRAND</div>
          <div className="metric-pill">{renderMetricPill(brandStatus)}</div>
        </div>
        <div>
          <div className="metric-label">VOLUME</div>
          <div className="metric-pill">{renderMetricPill(volumeStatus)}</div>
        </div>
        <div>
          <div className="metric-label">OSD</div>
          <div className="metric-pill">{renderMetricPill(osdStatus)}</div>
        </div>
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

      {testerNotes && (
        <div className="qs-summary-notes">
          <h4 className="metric-label">NOTES</h4>
          <p className="notes-text">{testerNotes}</p>
        </div>
      )}

      {shouldRenderDiagnostics && (
        <div className="qs-summary-diagnostics">
          {hasInsights && (
            <section className="qs-diagnostic-section">
              <h4>Why did it fail?</h4>
              <ul>
                {failureInsights.map((insight) => (
                  <li key={insight.code}>
                    <strong>{insight.title}</strong>
                    <div>{insight.description}</div>
                  </li>
                ))}
              </ul>
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
