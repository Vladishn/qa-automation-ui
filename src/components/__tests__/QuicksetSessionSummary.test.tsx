import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import QuicksetSessionSummary from '../QuicksetSessionSummary';
import type { TvAutoSyncSession, TvAutoSyncTimelineEvent, QuicksetAnalysisDetails } from '../../types/quickset';

const makeStep = (name: string, answer: string, status: 'PASS' | 'FAIL' | 'INFO' = 'PASS'): TvAutoSyncTimelineEvent => ({
  name,
  label: name,
  status,
  timestamp: '2025-12-08T06:45:23Z',
  question: null,
  user_answer: answer,
  details: { answer }
});

const makeSummary = (details: Partial<QuicksetAnalysisDetails>): TvAutoSyncTimelineEvent => ({
  name: 'analysis_summary',
  label: 'Scenario summary',
  status: (details.status as 'PASS' | 'FAIL' | 'INFO') ?? 'PASS',
  timestamp: '2025-12-08T06:45:55Z',
  question: null,
  user_answer: null,
  details: {
    analysis: details.analysis ?? 'TV auto-sync summary.',
    ...details
  }
});

const baseSession: TvAutoSyncSession = {
  session_id: 'QS_TEST',
  scenario_name: 'TV_AUTO_SYNC',
  overall_status: 'PASS',
  has_failure: false,
  brand_mismatch: false,
  has_volume_issue: false,
  has_osd_issue: false,
  brand_status: 'OK',
  volume_status: 'OK',
  osd_status: 'OK'
};

const baseTimeline: TvAutoSyncTimelineEvent[] = [
  makeStep('question_tv_volume_changed', 'yes'),
  makeStep('question_tv_osd_seen', 'yes'),
  makeStep('question_pairing_screen_seen', 'yes'),
  makeStep('question_tv_brand_ui', 'LG')
];

describe('QuicksetSessionSummary', () => {
  it('shows tester vs telemetry context and inconclusive warning when logs are unknown', () => {
    const session: TvAutoSyncSession = {
      ...baseSession,
      volume_status: 'INCOMPATIBILITY',
      osd_status: 'INCOMPATIBILITY',
      analysis_text:
        'TV auto-sync functional criteria passed (tester confirmed volume, OSD, and pairing). Telemetry probe was inconclusive – no TV responses observed.'
    };
    const timeline: TvAutoSyncTimelineEvent[] = [
      ...baseTimeline,
      makeSummary({
        tester_verdict: 'PASS',
        log_verdict: 'INCONCLUSIVE',
        telemetry_state: 'UNKNOWN',
        conflict_tester_vs_logs: false,
        autosync_started: false,
        autosync_success: false,
        evidence: {
          tv_volume_events: false,
          tv_osd_events: false,
          volume_probe_state: 'UNKNOWN'
        }
      })
    ];

    render(<QuicksetSessionSummary session={session} timeline={timeline} metricStatuses={null} />);

    expect(screen.getByText('TESTER SIGNALS')).toBeInTheDocument();
    expect(screen.getByText('LOGS & TELEMETRY')).toBeInTheDocument();
    expect(screen.getByText('Overall tester verdict')).toBeInTheDocument();
    expect(screen.getByText('Log verdict')).toBeInTheDocument();
    expect(
      screen.getByText(/Logs\/telemetry inconclusive; relying on tester answers/i)
    ).toBeInTheDocument();
  });

  it('highlights brand mismatch details provided by backend', () => {
    const session: TvAutoSyncSession = {
      ...baseSession,
      overall_status: 'FAIL',
      has_failure: true,
      brand_mismatch: true,
      brand_status: 'INCOMPATIBILITY',
      tv_brand_user: 'LG',
      tv_brand_log: 'Samsung'
    };
    const timeline: TvAutoSyncTimelineEvent[] = [
      ...baseTimeline,
      makeSummary({
        tester_verdict: 'PASS',
        log_verdict: 'PASS',
        telemetry_state: 'TV_CONTROL',
        conflict_tester_vs_logs: false
      })
    ];

    render(<QuicksetSessionSummary session={session} timeline={timeline} metricStatuses={null} />);

    expect(
      screen.getByText(/Brand mismatch: tester saw "LG", logs say "Samsung"./i)
    ).toBeInTheDocument();
  });

  it('shows conflict section when logs contradict tester', () => {
    const session: TvAutoSyncSession = {
      ...baseSession,
      overall_status: 'FAIL',
      has_failure: true,
      volume_status: 'INCOMPATIBILITY',
      osd_status: 'INCOMPATIBILITY',
      has_volume_issue: true,
      has_osd_issue: true,
      analysis_text: 'TV auto-sync failed: telemetry indicates STB control.'
    };
    const timeline: TvAutoSyncTimelineEvent[] = [
      ...baseTimeline,
      makeSummary({
        tester_verdict: 'PASS',
        log_verdict: 'FAIL',
        telemetry_state: 'STB_CONTROL_CONFIDENT',
        conflict_tester_vs_logs: true,
        log_failure_reason: 'Telemetry indicates STB controls volume/OSD.',
        evidence: {
          volume_probe_state: 'STB',
          volume_probe_confidence: 0.9
        }
      })
    ];

    render(<QuicksetSessionSummary session={session} timeline={timeline} metricStatuses={null} />);

    expect(
      screen.getByText(/Conflict detected: Tester vs logs\/telemetry/i)
    ).toBeInTheDocument();
    const conflictMessages = screen.getAllByText(/Telemetry indicates STB controls volume\/OSD./i);
    expect(conflictMessages.length).toBeGreaterThan(0);
  });
});
