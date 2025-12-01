// src/api/client.ts
import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_QUICKSET_API_BASE_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: API_BASE_URL,
});

export type ScenarioName = "TV_AUTO_SYNC";

export interface RunScenarioRequest {
  testerId: string;
  stbIp: string;
  scenarioName: ScenarioName;
}

export interface Step {
  step: string;
  status: "pending" | "running" | "pass" | "fail";
  timestamp?: string;
  metadata: Record<string, unknown>;
}

export interface Session {
  session_id: string;
  tester_id: string;
  stb_ip: string;
  scenario_name: ScenarioName;
  start_time: string;
  end_time?: string;
  steps: Step[];
  result?: "pass" | "fail";
  logs: {
    adb?: string;
    logcat?: string;
    [key: string]: unknown;
  };
}

export interface RunScenarioResponse {
  session_id: string;
  scenario_name: ScenarioName;
}

export async function runScenario(
  payload: RunScenarioRequest,
  apiKey: string
): Promise<RunScenarioResponse> {
  const res = await api.post<RunScenarioResponse>(
    "/qa/scenarios/run",
    {
      tester_id: payload.testerId,
      stb_ip: payload.stbIp,
      scenario_name: payload.scenarioName,
    },
    {
      headers: {
        "X-QuickSet-Api-Key": apiKey,
      },
    }
  );
  return res.data;
}

export async function getSession(sessionId: string, apiKey: string): Promise<Session> {
  const res = await api.get<Session>(`/session/${sessionId}`, {
    headers: {
      "X-QuickSet-Api-Key": apiKey,
    },
  });
  return res.data;
}
