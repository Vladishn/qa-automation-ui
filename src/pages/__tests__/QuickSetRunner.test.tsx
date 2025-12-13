import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import QuickSetRunner from '../QuickSetRunner';
import type { TvAutoSyncSessionResponse } from '../../types/quickset';
import { useSessionPolling } from '../../hooks/useSessionPolling';
import { runScenario } from '../../services/quicksetService';

jest.mock('../../hooks/useSessionPolling');
jest.mock('../../services/quicksetService');
jest.mock('../../components/fields/StbIpField', () => {
  const MockField: React.FC<{ value: string; onChange: (value: string) => void; disabled?: boolean }> = ({
    value,
    onChange,
    disabled
  }) => (
    <input
      aria-label="STB IP"
      value={value}
      onChange={(event) => onChange(event.target.value)}
      disabled={disabled}
    />
  );
  return {
    __esModule: true,
    StbIpField: MockField,
    default: MockField
  };
});

const mockUseSessionPolling = useSessionPolling as jest.MockedFunction<typeof useSessionPolling>;
const mockRunScenario = runScenario as jest.MockedFunction<typeof runScenario>;

const buildSessionPayload = (sessionId: string, scenarioName: string): TvAutoSyncSessionResponse => ({
  session: {
    session_id: sessionId,
    scenario_name: scenarioName,
    started_at: '2024-01-01T00:00:00Z',
    finished_at: '2024-01-01T00:10:00Z',
    overall_status: 'PASS',
    has_failure: false,
    brand_mismatch: false,
    tv_brand_user: null,
    tv_brand_log: null,
    has_volume_issue: false,
    has_osd_issue: false,
    analysis_text: 'Done',
    notes: null,
    analyzer_ready: true,
    brand_status: 'OK',
    volume_status: 'OK',
    osd_status: 'OK'
  },
  timeline: [
    {
      name: 'analysis_summary',
      label: 'Scenario summary',
      status: 'PASS',
      timestamp: '2024-01-01T00:10:00Z',
      details: {
        analysis: 'All good',
        failure_insights: [],
        recommendations: []
      }
    }
  ],
  has_failure: false,
  quickset_session: {
    session_id: sessionId,
    tester_id: 'tester-id',
    stb_ip: '1.2.3.4',
    scenario_name: scenarioName,
    state: 'completed',
    pending_question: null,
    infra_checks: [],
    logs: { adb: '', logcat: '' }
  }
});

describe('QuickSetRunner scenario switching', () => {
  const sessionPayloads: Record<string, TvAutoSyncSessionResponse> = {};

  beforeEach(() => {
    jest.clearAllMocks();
    for (const key of Object.keys(sessionPayloads)) {
      delete sessionPayloads[key];
    }
    mockUseSessionPolling.mockImplementation((sessionId: string | null) => {
      const data = sessionId ? sessionPayloads[sessionId] ?? null : null;
      return { data, error: null, setData: jest.fn() };
    });
  });

  it('clears summary when switching to a scenario without a session and shows completion indicator only for active scenario', async () => {
    sessionPayloads.TV_SESSION = buildSessionPayload('TV_SESSION', 'TV_AUTO_SYNC');
    mockRunScenario.mockResolvedValue({
      session_id: 'TV_SESSION',
      scenario_name: 'TV_AUTO_SYNC'
    });

    render(<QuickSetRunner />);

    fireEvent.change(screen.getByLabelText('Tester ID'), { target: { value: 'tester-01' } });
    fireEvent.change(screen.getByLabelText('STB IP'), { target: { value: '10.0.0.1' } });
    fireEvent.change(screen.getByLabelText('API Key'), { target: { value: 'secret' } });

    await waitFor(() => expect(screen.getByRole('button', { name: /Start test/i })).toBeEnabled());

    fireEvent.click(screen.getByRole('button', { name: /Start test/i }));
    await waitFor(() => expect(mockRunScenario).toHaveBeenCalledTimes(1));

    await screen.findByText(/Session TV_SESSION/);
    expect(screen.getByText(/Test completed for session TV_SESSION/)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Scenario'), {
      target: { value: 'LIVE_BUTTON_MAPPING' }
    });

    await waitFor(() => {
      expect(screen.queryByText(/Session TV_SESSION/)).not.toBeInTheDocument();
    });
    expect(
      screen.getByText('Run a session to see the QuickSet analysis summary.')
    ).toBeInTheDocument();
    expect(screen.queryByText(/Test completed for session/)).not.toBeInTheDocument();
  });

  it('renders expected channel field for Live Button Mapping and sends value to backend', async () => {
    mockRunScenario.mockResolvedValue({
      session_id: 'LIVE_SESSION',
      scenario_name: 'LIVE_BUTTON_MAPPING'
    });
    render(<QuickSetRunner />);

    expect(screen.queryByLabelText('Expected channel')).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Scenario'), {
      target: { value: 'LIVE_BUTTON_MAPPING' }
    });
    const expectedChannelInput = screen.getByLabelText('Expected channel') as HTMLInputElement;
    expect(expectedChannelInput.value).toBe('3');
    fireEvent.change(expectedChannelInput, { target: { value: '15' } });

    fireEvent.change(screen.getByLabelText('Tester ID'), { target: { value: 'tester-live' } });
    fireEvent.change(screen.getByLabelText('STB IP'), { target: { value: '10.0.0.9' } });
    fireEvent.change(screen.getByLabelText('API Key'), { target: { value: 'abc123' } });

    fireEvent.click(screen.getByRole('button', { name: /Start test/i }));

    await waitFor(() => expect(mockRunScenario).toHaveBeenCalled());
    expect(mockRunScenario).toHaveBeenLastCalledWith(
      expect.objectContaining({
        scenarioName: 'LIVE_BUTTON_MAPPING',
        expectedChannel: 15
      })
    );
  });
});
