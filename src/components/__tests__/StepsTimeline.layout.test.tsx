import React from 'react';
import { render } from '@testing-library/react';
import '@testing-library/jest-dom';
import { StepsTimeline } from '../StepsTimeline';
import type { TvAutoSyncTimelineEvent } from '../../types/quickset';

const sampleRows: TvAutoSyncTimelineEvent[] = [
  {
    name: 'question_tv_volume_changed',
    label: 'TV volume changed',
    status: 'FAIL',
    timestamp: '2025-12-07T14:55:53.000Z',
    question: 'Did the TV volume change?',
    user_answer: 'Yes',
    details: {
      analysis: 'Analyzer saw inconsistent TV volume events.',
      probe_mismatch_reason: 'Probe indicates STB controls TV volume.'
    }
  },
  {
    name: 'question_tv_osd_seen',
    label: 'TV OSD seen',
    status: 'INFO',
    timestamp: '2025-12-07T14:56:13.000Z',
    question: 'Did you see the TV OSD?',
    user_answer: 'Yes',
    details: {
      analysis: 'Telemetry inconclusive – no TV OSD frames detected.'
    }
  },
  {
    name: 'analysis_summary',
    label: 'Scenario summary',
    status: 'PASS',
    timestamp: '2025-12-07T14:57:10.000Z',
    question: null,
    user_answer: null,
    details: {
      analysis:
        'TV auto-sync failed: no TV responses observed (no volume change, no TV OSD). ' +
        'Failed steps: question_tv_volume_changed, question_tv_osd_seen',
      tester_verdict: 'PASS',
      log_verdict: 'INCONCLUSIVE',
      telemetry_state: 'UNKNOWN',
      conflict_tester_vs_logs: false,
      log_failure_reason: 'Logs were inconclusive for TV control.'
    }
  }
];

describe('StepsTimeline layout', () => {
  it('renders 4-column step rows with info kept inside the QA card', () => {
    const { container } = render(
      <div className="card qa-card">
        <StepsTimeline sessionId="session-123" rows={sampleRows} />
      </div>
    );

    const header = container.querySelector('.qa-grid-4cols.qa-grid-4cols-header');
    expect(header).toBeInTheDocument();
    expect(header?.children).toHaveLength(4);
    const headerLabels = Array.from(header!.children).map((cell) =>
      cell.textContent?.trim().toLowerCase()
    );
    expect(headerLabels).toEqual(['step', 'status', 'timestamp', 'info']);

    const rowElements = container.querySelectorAll('.qa-step-row');
    expect(rowElements).toHaveLength(sampleRows.length);

    rowElements.forEach((rowEl, idx) => {
      const cells = Array.from(rowEl.children) as HTMLElement[];
      expect(cells).toHaveLength(4);

      const [stepCell, statusCell, timestampCell, infoCell] = cells;

      expect(stepCell).toHaveClass('qa-col-text');
      expect(stepCell.textContent?.trim().length).toBeGreaterThan(0);

      const pill = statusCell.querySelector('.status-pill');
      expect(pill).toBeInTheDocument();
      const expectedStatus = sampleRows[idx].status.toUpperCase();
      expect(pill?.textContent?.trim().toUpperCase()).toBe(expectedStatus);

      expect(timestampCell).toHaveClass('qa-col-timestamp');
      expect(timestampCell.textContent?.trim().length).toBeGreaterThan(0);

      expect(infoCell).toHaveClass('qa-col-text-sm');
      expect(infoCell).toHaveClass('qa-step-info');
      expect(infoCell.textContent?.trim().length).toBeGreaterThan(0);

      const containingCard = rowEl.closest('.qa-card');
      expect(containingCard).toBeInTheDocument();
      expect(containingCard?.contains(infoCell)).toBe(true);
    });

    const hasVolumeRow = Array.from(rowElements).some((rowEl) =>
      rowEl.textContent?.toLowerCase().includes('tv volume changed')
    );
    expect(hasVolumeRow).toBe(true);

    const mismatchInfo = Array.from(rowElements).some((rowEl) =>
      rowEl.textContent?.toLowerCase().includes('probe indicates stb controls')
    );
    expect(mismatchInfo).toBe(true);

    const summaryInfo = Array.from(rowElements).some((rowEl) =>
      rowEl.textContent?.toLowerCase().includes('tester verdict')
    );
    expect(summaryInfo).toBe(true);
  });
});
