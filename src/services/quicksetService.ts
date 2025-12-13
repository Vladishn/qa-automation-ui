import { apiGet, apiPost } from './httpClient';
import type { QuickSetSession } from '../types/domain';
import type { TvAutoSyncSessionResponse } from '../types/quickset';

export type QuicksetScenarioId = 'TV_AUTO_SYNC' | 'LIVE_BUTTON_MAPPING';

export interface RunScenarioParams {
  testerId: string;
  stbIp: string;
  apiKey: string;
  scenarioName: QuicksetScenarioId;
  expectedChannel?: number;
}

export interface RunScenarioResponse {
  session_id: string;
  scenario_name: string;
}

export async function runScenario(params: RunScenarioParams): Promise<RunScenarioResponse> {
  const { testerId, stbIp, apiKey, scenarioName, expectedChannel } = params;
  const body: Record<string, unknown> = {
    tester_id: testerId,
    stb_ip: stbIp,
    scenario_name: scenarioName
  };
  if (typeof expectedChannel === 'number') {
    body.expected_channel = expectedChannel;
  }
  return apiPost<RunScenarioResponse>(
    '/api/quickset/scenarios/run',
    body,
    {
      headers: {
        'X-QuickSet-Api-Key': apiKey,
      },
    }
  );
}

export async function getSession(
  sessionId: string,
  apiKey: string,
  signal?: AbortSignal
): Promise<TvAutoSyncSessionResponse> {
  return apiGet<TvAutoSyncSessionResponse>(`/api/quickset/sessions/${sessionId}`, undefined, {
    headers: {
      'X-QuickSet-Api-Key': apiKey,
    },
    signal,
  });
}

export async function answerQuestion(sessionId: string, apiKey: string, answer: string): Promise<QuickSetSession> {
  return apiPost<QuickSetSession>(
    `/api/quickset/sessions/${sessionId}/answer`,
    { answer },
    {
      headers: {
        'X-QuickSet-Api-Key': apiKey,
      },
    }
  );
}
