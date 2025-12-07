import React from 'react';
import type { AnalyzerStepStatus, MetricTriState, TvAutoSyncTimelineEvent } from '../types/quickset';
import { formatTriStateLabel } from '../logic/quicksetMetrics';
import './StepsTimeline.css';

interface Props {
  sessionId?: string | null;
  rows: TimelineRow[] | null;
  isLoading?: boolean;
  error?: string | null;
}

type TimelineStatus = AnalyzerStepStatus | MetricTriState;
type TimelineRow = TvAutoSyncTimelineEvent & { statusDisplay?: TimelineStatus };

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
    const failedSteps = details.failed_steps as string[] | undefined;
    const awaitingSteps = details.awaiting_steps as string[] | undefined;
    if (row.status === 'FAIL' && Array.isArray(failedSteps) && failedSteps.length) {
      parts.push(`Failed steps: ${failedSteps.join(', ')}`);
    }
    if (row.status === 'FAIL' && Array.isArray(awaitingSteps) && awaitingSteps.length) {
      parts.push(`Awaiting: ${awaitingSteps.join(', ')}`);
    }
  } else if (row.status === 'FAIL') {
    ['mismatch_reason', 'analysis', 'note'].forEach((key) => {
      const value = details[key];
      if (typeof value === 'string' && value.trim()) {
        parts.push(value.trim());
      }
    });
  }

  return parts.length ? parts.join('\n') : '—';
};

const StepsTimeline: React.FC<Props> = ({ sessionId, rows, isLoading, error }) => {
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
    <div className="steps-timeline-container">
      <div className="space-y-3 text-sm">
        <div className={`qa-grid-4cols qa-grid-4cols-header px-6`}>
          <div className="text-left">Step</div>
          <div className="text-center">Status</div>
          <div className="text-right">Timestamp</div>
          <div className="text-left">Info</div>
        </div>

        <div className="mt-3 space-y-1">
          {timelineRows.map((row, index) => {
            const key = `${row.name}-${row.timestamp ?? index}`;
            const label = row.label || row.name;
            const timestampText = row.timestamp ? new Date(row.timestamp).toLocaleString() : '—';
            const infoText = buildInfo(row);

            const displayStatus = (row.statusDisplay ?? row.status) as TimelineStatus;
            const pillLabel = formatStatusText(displayStatus);
            const pillStyle = displayStatus === 'INCOMPATIBILITY' ? warningPillStyle : undefined;

            return (
              <div
                key={key}
                className={`qa-grid-4cols qa-grid-4cols-row px-6`}
              >
                <div className="qa-col-text">{label}</div>
                <div className="flex justify-center">
                  <span className="qa-col-pill">
                    <span className={statusClass(displayStatus)} style={pillStyle}>
                      {pillLabel}
                    </span>
                  </span>
                </div>
                <div className="qa-col-timestamp">{timestampText}</div>
                <div className="qa-col-text-sm">{infoText}</div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default StepsTimeline;
