import React from 'react';
import type { TimelineRow, TimelineStepStatus } from '../types/domain';
import './StepsTimeline.css';

interface Props {
  sessionId?: string | null;
  rows: TimelineRow[] | null;
  isLoading?: boolean;
  error?: string | null;
}

const statusClass = (status: TimelineStepStatus): string => {
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
      <div className="steps-timeline-scroll">
        <table className="steps-timeline-table">
          <thead>
            <tr>
              <th className="steps-timeline-col-step">Step</th>
              <th className="steps-timeline-col-status">Status</th>
              <th className="steps-timeline-col-timestamp">Timestamp</th>
              <th className="steps-timeline-col-info">Info</th>
            </tr>
          </thead>
          <tbody>
            {timelineRows.map((row, index) => (
              <tr key={`${row.name}-${row.timestamp ?? index}`}>
                <td className="steps-timeline-col-step">{row.label || row.name}</td>
                <td className="steps-timeline-col-status">
                  <span className={statusClass(row.status)}>{row.status}</span>
                </td>
                <td className="steps-timeline-col-timestamp">
                  {row.timestamp ? new Date(row.timestamp).toLocaleString() : '—'}
                </td>
                <td className="steps-timeline-col-info">{buildInfo(row)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default StepsTimeline;
