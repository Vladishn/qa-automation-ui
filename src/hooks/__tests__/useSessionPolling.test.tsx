import React, { useEffect } from 'react';
import { act, render } from '@testing-library/react';
import { useSessionPolling } from '../useSessionPolling';
import { getSession } from '../../services/quicksetService';
import type { TvAutoSyncSessionResponse } from '../../types/quickset';

jest.mock('../../services/quicksetService');

const mockGetSession = getSession as jest.MockedFunction<typeof getSession>;

const buildResponse = (sessionId: string, finished = false): TvAutoSyncSessionResponse => ({
  session: {
    session_id: sessionId,
    scenario_name: 'TV_AUTO_SYNC',
    started_at: '2024-01-01T00:00:00Z',
    finished_at: finished ? '2024-01-01T00:05:00Z' : null,
    overall_status: finished ? 'PASS' : 'PENDING',
    has_failure: false,
    brand_mismatch: false,
    tv_brand_user: null,
    tv_brand_log: null,
    has_volume_issue: false,
    has_osd_issue: false,
    analysis_text: '',
    notes: null,
    analyzer_ready: finished,
    brand_status: 'OK',
    volume_status: 'OK',
    osd_status: 'OK'
  },
  timeline: [],
  has_failure: false,
  quickset_session: {
    session_id: sessionId,
    tester_id: 'tester',
    stb_ip: '1.2.3.4',
    scenario_name: 'TV_AUTO_SYNC',
    state: finished ? 'completed' : 'running',
    pending_question: null,
    infra_checks: [],
    logs: { adb: '', logcat: '' }
  }
});

type HookResult = ReturnType<typeof useSessionPolling>;

const HookWrapper: React.FC<{
  sessionId: string | null;
  apiKey: string | null;
  capture: (value: HookResult) => void;
}> = ({ sessionId, apiKey, capture }) => {
  const result = useSessionPolling(sessionId, apiKey);
  useEffect(() => {
    capture(result);
  }, [result, capture]);
  return null;
};

describe('useSessionPolling', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    jest.clearAllMocks();
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
  });

  it('stops polling when sessionId becomes null', async () => {
    mockGetSession.mockResolvedValue(buildResponse('session-a'));
    const latest: { current: HookResult | null } = { current: null };
    const capture = (value: HookResult) => {
      latest.current = value;
    };

    const { rerender } = render(<HookWrapper sessionId={null} apiKey="key" capture={capture} />);

    expect(mockGetSession).not.toHaveBeenCalled();

    await act(async () => {
      rerender(<HookWrapper sessionId="session-a" apiKey="key" capture={capture} />);
    });

    expect(mockGetSession).toHaveBeenCalledTimes(1);

    await act(async () => {
      rerender(<HookWrapper sessionId={null} apiKey="key" capture={capture} />);
    });

    expect(latest.current?.data).toBeNull();

    jest.advanceTimersByTime(4000);
    expect(mockGetSession).toHaveBeenCalledTimes(1);
  });

  it('ignores stale responses when switching sessions', async () => {
    const resolvers: Record<string, (value: TvAutoSyncSessionResponse) => void> = {};
    mockGetSession.mockImplementation(
      (sessionId: string) =>
        new Promise<TvAutoSyncSessionResponse>((resolve) => {
          resolvers[sessionId] = resolve;
        })
    );
    const latest: { current: HookResult | null } = { current: null };
    const capture = (value: HookResult) => {
      latest.current = value;
    };

    const { rerender } = render(<HookWrapper sessionId="first" apiKey="key" capture={capture} />);

    await act(async () => {
      rerender(<HookWrapper sessionId="second" apiKey="key" capture={capture} />);
    });

    const firstResolver = resolvers.first;
    expect(firstResolver).toBeDefined();
    await act(async () => {
      firstResolver?.(buildResponse('first'));
    });

    expect(latest.current?.data).toBeNull();

    const secondResolver = resolvers.second;
    expect(secondResolver).toBeDefined();
    await act(async () => {
      secondResolver?.(buildResponse('second'));
    });

    expect(latest.current?.data?.session.session_id).toBe('second');
  });
});
