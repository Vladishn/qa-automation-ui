import React from 'react';
import type { SessionSummary, TimelineRow, TimelineStepStatus } from '../types/domain';
import './QuicksetSessionSummary.css';

interface Props {
  session: SessionSummary;
  timeline: TimelineRow[];
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

type StatusVariant = 'success' | 'danger' | 'neutral';
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
    default:
      return 'status-pill status-pill--info';
  }
};

const renderStatusValue = (status: StatusDescriptor) => (
  <div>
    <span className={pillClassForVariant(status.variant)}>{status.label}</span>
    {status.detail && <div className="qs-summary-detail">{status.detail}</div>}
  </div>
);

const SummaryRow: React.FC<{ label: string; value: React.ReactNode }> = ({ label, value }) => (
  <div className="qs-summary-row">
    <dt>{label}</dt>
    <dd>{value}</dd>
  </div>
);

const QuicksetSessionSummary: React.FC<Props> = ({ session }) => {
  const scenarioTitle = session.scenario_name && session.scenario_name !== 'UNKNOWN'
    ? session.scenario_name
    : 'TV_AUTO_SYNC';

  const overall = session.overall_status;
  const awaiting = overall === 'AWAITING_INPUT';
  const badgeLabel = awaiting ? 'AWAITING INPUT' : overall;
  const badgeStatus = awaiting ? 'AWAITING_INPUT' : overall;

  const uiBrand = (session.tv_brand_user ?? '').trim();
  const logBrand = (session.tv_brand_log ?? '').trim();
  const hasUiBrand = uiBrand.length > 0;
  const hasLogBrand = logBrand.length > 0;
  const brandMismatch = session.brand_mismatch === true;

  let brandStatus: StatusDescriptor = { label: 'Not evaluated yet', variant: 'neutral', detail: 'Not evaluated yet' };
  if (brandMismatch) {
    const uiText = hasUiBrand ? uiBrand : 'not provided';
    const logText = hasLogBrand ? logBrand : 'not detected';
    brandStatus = { label: 'FAIL', variant: 'danger', detail: `UI: ${uiText} / Logs: ${logText}` };
  } else if (hasLogBrand || hasUiBrand) {
    const brandText = hasLogBrand ? logBrand : uiBrand;
    brandStatus = { label: 'OK', variant: 'success', detail: brandText ? `OK – ${brandText}` : undefined };
  }

  const volumeStatus: StatusDescriptor = (() => {
    if (session.has_volume_issue) {
      return { label: 'FAIL', variant: 'danger', detail: 'Issue detected' };
    }
    if (awaiting) {
      return { label: 'Not evaluated yet', variant: 'neutral', detail: 'Awaiting tester input' };
    }
    return { label: 'OK', variant: 'success', detail: 'OK' };
  })();

  const osdStatus: StatusDescriptor = (() => {
    if (session.has_osd_issue) {
      return { label: 'FAIL', variant: 'danger', detail: 'Issue detected' };
    }
    if (awaiting) {
      return { label: 'Not evaluated yet', variant: 'neutral', detail: 'Awaiting tester input' };
    }
    return { label: 'OK', variant: 'success', detail: 'OK' };
  })();

  const rawNotes = (session.notes || '').trim();
  const notesStatus: StatusDescriptor = rawNotes && rawNotes.toLowerCase() !== 'no'
    ? { label: 'OK', variant: 'success', detail: rawNotes }
    : { label: 'Not evaluated yet', variant: 'neutral', detail: 'Not evaluated yet' };

  return (
    <div className="qs-summary">
      <div className="qs-summary-header">
        <div>
          <div className="qs-summary-title">{scenarioTitle}</div>
          <div className="qs-summary-subtitle">Session {session.session_id}</div>
        </div>
        <span className={statusClass(badgeStatus)}>{badgeLabel}</span>
      </div>

      <p className="qs-summary-analysis">{session.analysis_text}</p>

      <dl className="qs-summary-grid">
        <SummaryRow label="Brand" value={renderStatusValue(brandStatus)} />
        <SummaryRow label="Volume" value={renderStatusValue(volumeStatus)} />
        <SummaryRow label="OSD" value={renderStatusValue(osdStatus)} />
        <SummaryRow label="Notes" value={renderStatusValue(notesStatus)} />
      </dl>
    </div>
  );
};

export default QuicksetSessionSummary;
