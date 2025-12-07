import { apiGet, apiPost } from './httpClient';
import type { QuickSetSession } from '../types/domain';
import type { TvAutoSyncSessionResponse } from '../types/quickset';

export interface RunScenarioParams {
  testerId: string;
  stbIp: string;
  apiKey: string;
  scenarioName: 'TV_AUTO_SYNC';
}

export interface RunScenarioResponse {
  session_id: string;
  scenario_name: string;
}

export async function runScenario(params: RunScenarioParams): Promise<RunScenarioResponse> {
  const { testerId, stbIp, apiKey, scenarioName } = params;
  return apiPost<RunScenarioResponse>(
    '/api/quickset/scenarios/run',
    {
      tester_id: testerId,
      stb_ip: stbIp,
      scenario_name: scenarioName,
    },
    {
      headers: {
        'X-QuickSet-Api-Key': apiKey,
      },
    }
  );
}

export async function getSession(sessionId: string, apiKey: string): Promise<TvAutoSyncSessionResponse> {
  return apiGet<TvAutoSyncSessionResponse>(`/api/quickset/sessions/${sessionId}`, undefined, {
    headers: {
      'X-QuickSet-Api-Key': apiKey,
    },
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
