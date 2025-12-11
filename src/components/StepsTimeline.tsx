import React from 'react';
import type {
  AnalyzerStepStatus,
  MetricTriState,
  TvAutoSyncTimelineEvent
} from '../types/quickset';
import { formatTriStateLabel } from '../logic/quicksetMetrics';
import './StepsTimeline.css';

interface Props {
  sessionId?: string | null;
  rows: TimelineRow[] | null;
  isLoading?: boolean;
  error?: string | null;
}

type TimelineStatus = AnalyzerStepStatus | MetricTriState;
type TimelineRow = TvAutoSyncTimelineEvent;

const GRID_TEMPLATE =
  'grid grid-cols-[minmax(150px,1.1fr)_minmax(90px,0.7fr)_minmax(190px,1fr)_minmax(300px,1.9fr)] gap-x-6';

const warningPillStyle: React.CSSProperties = {
  background: 'rgba(251, 191, 36, 0.18)',
  color: '#fbbf24'
};

const statusClass = (status: TimelineStatus): string => {
  switch (status) {
    case 'OK':
    case 'PASS':
      return 'status-pill status-pill--pass';
    case 'FAIL':
      return 'status-pill status-pill--fail';
    case 'INCOMPATIBILITY':
      return 'status-pill status-pill--info';
    case 'PENDING':
    case 'AWAITING_INPUT':
      return 'status-pill status-pill--running';
    case 'NOT_EVALUATED':
      return 'status-pill status-pill--info';
    default:
      return 'status-pill status-pill--info';
  }
};

const isTriStateStatus = (value: TimelineStatus): value is MetricTriState =>
  value === 'OK' || value === 'FAIL' || value === 'INCOMPATIBILITY' || value === 'NOT_EVALUATED';

const formatStatusText = (status: TimelineStatus): string =>
  isTriStateStatus(status) ? formatTriStateLabel(status) : status;

const buildInfo = (row: TimelineRow): string => {
  const parts: string[] = [];

  if (row.question) {
    parts.push(row.question.trim());
  }
  if (row.user_answer) {
    parts.push(`Answer: ${row.user_answer.trim()}`);
  }

  const details = (row.details ?? {}) as Record<string, unknown>;

  if (row.name === 'analysis_summary') {
    const summaryAnalysis = details.analysis;
    if (typeof summaryAnalysis === 'string' && summaryAnalysis.trim()) {
      parts.push(summaryAnalysis.trim());
    }

    const testerVerdict = details.tester_verdict;
    const logVerdict = details.log_verdict;
    const telemetryState = details.telemetry_state;

    if (testerVerdict) {
      parts.push(`Tester verdict: ${testerVerdict}`);
    }
    if (logVerdict) {
      parts.push(`Log verdict: ${logVerdict}`);
    }
    if (telemetryState) {
      parts.push(`Telemetry state: ${telemetryState}`);
    }

    const conflict = details.conflict_tester_vs_logs;
    if (typeof conflict === 'boolean') {
      parts.push(`Conflict (tester vs logs): ${conflict ? 'YES' : 'NO'}`);
    }

    const failureReason = details.log_failure_reason;
    if (typeof failureReason === 'string' && failureReason.trim()) {
      parts.push(`Log finding: ${failureReason.trim()}`);
    }

    const failedSteps = details.failed_steps as string[] | undefined;
    const awaitingSteps = details.awaiting_steps as string[] | undefined;

    if (row.status === 'FAIL' && Array.isArray(failedSteps) && failedSteps.length) {
      parts.push(`Failed steps: ${failedSteps.join(', ')}`);
    }
    if (row.status === 'FAIL' && Array.isArray(awaitingSteps) && awaitingSteps.length) {
      parts.push(`Awaiting: ${awaitingSteps.join(', ')}`);
    }
  } else {
    ['mismatch_reason', 'analysis', 'note', 'probe_mismatch_reason'].forEach((key) => {
      const value = details[key];
      if (typeof value === 'string' && value.trim()) {
        parts.push(value.trim());
      }
    });

    if (details.issue_confirmed_by_probe) {
      parts.push('Probe confirmed this issue.');
    }

    const detectionState = details.volume_probe_detection_state;
    if (typeof detectionState === 'string' && detectionState.trim()) {
      parts.push(`Probe detection state: ${detectionState}`);
    }

    const probeState = details.volume_probe_state;
    const probeConfidence = details.volume_probe_confidence;

    if (typeof probeState === 'string') {
      const confidenceText =
        typeof probeConfidence === 'number' ? ` (confidence ${probeConfidence})` : '';
      parts.push(`Probe source: ${probeState}${confidenceText}`);
    }
  }

  return parts.length ? parts.join('\n') : '—';
};

export const StepsTimeline: React.FC<Props> = ({ sessionId, rows, isLoading, error }) => {
  const timelineRows = rows ?? [];

  if (!sessionId) {
    return <p className="hint">Steps will appear once the run starts.</p>;
  }

  if (isLoading && !rows) {
    return <p className="hint">Loading timeline…</p>;
  }

  if (error) {
    return (
      <p className="hint" style={{ color: '#ff8a8a' }}>
        Failed to load timeline: {error}
      </p>
    );
  }

  if (!rows || timelineRows.length === 0) {
    return <p className="hint">No timeline data yet.</p>;
  }

  return (
    <div className="steps-timeline-container flex flex-col text-sm text-slate-100">
      <div className="overflow-x-auto flex-1 min-h-0">
        <div className="min-w-[980px]">
          {/* Header row */}
          <div
            className={`${GRID_TEMPLATE} qa-grid-4cols qa-grid-4cols-header items-center border-b border-slate-800 px-6 py-3 text-[11px] font-semibold uppercase tracking-wide text-slate-400`}
          >
            <div className="text-left">Step</div>
            <div className="text-left">Status</div>
            <div className="text-left">Timestamp</div>
            <div className="text-left">Info</div>
          </div>

          {/* Data rows */}
          <div className="divide-y divide-slate-800">
            {timelineRows.map((row, index) => {
              const key = `${row.name}-${row.timestamp ?? index}`;
              const status = row.status as TimelineStatus;
              const pillLabel = formatStatusText(status);
              const pillStyle = status === 'INCOMPATIBILITY' ? warningPillStyle : undefined;
              const stepLabel =
                row.label ?? ((row as { step_label?: string }).step_label ?? row.name);
              const timestampValue = row.timestamp
                ? new Date(row.timestamp).toLocaleString()
                : '—';
              const infoField = (row as { info?: string }).info;
              const infoValue = infoField ?? buildInfo(row);

              return (
                <div
                  key={key}
                  className={`${GRID_TEMPLATE} qa-grid-4cols qa-grid-4cols-row qa-step-row items-start px-6 py-3 text-[12px]`}
                >
                  <div className="qa-col-text text-left text-slate-100 truncate">{stepLabel}</div>
                  <div className="qa-col-pill flex justify-start">
                    <span className={statusClass(status)} style={pillStyle}>
                      {pillLabel}
                    </span>
                  </div>
                  <div className="qa-col-timestamp text-left text-[11px] text-slate-400 whitespace-nowrap">
                    {timestampValue}
                  </div>
                  <div className="qa-col-text-sm qa-step-info text-left text-[11px] leading-relaxed text-slate-300 whitespace-pre-wrap break-words">
                    {infoValue}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};

export default StepsTimeline;
