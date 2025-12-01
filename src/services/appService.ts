// src/services/appService.ts
// Application test data helpers with backend-aware loaders plus local fallbacks.

import { apiGet, logApiError } from './httpClient';
import type {
  Platform,
  PlatformId,
  TestRunSummary,
  TestScenario,
  TestStepIssue,
  VersionUnderTest
} from '../types/domain';

const APP_VERSIONS_KEY = 'app_versions_v1';

export const APP_PLATFORMS: Platform[] = [
  { id: 'S70PCI_FW', label: 'STB Sys App · S70PCI', family: 'STB', vendor: 'Ventiva', model: 'S70PCI' },
  { id: 'JADE_FW', label: 'STB Sys App · Jade', family: 'STB', vendor: 'Ventiva', model: 'JADE' },
  { id: 'SEI_X4_FW', label: 'STB Sys App · SEI X4', family: 'STB', vendor: 'SEI', model: 'SEI_X4' },
  { id: 'ANDROID_TV_VSTB', label: 'Android TV · vSTB', family: 'VSTB', vendor: 'Google' },
  { id: 'ANDROID_MOBILE', label: 'Android Mobile', family: 'MOBILE', vendor: 'Google' },
  { id: 'SMART_TV_LG', label: 'Smart TV · LG', family: 'SMART_TV', vendor: 'LG' },
  { id: 'SMART_TV_SAMSUNG', label: 'Smart TV · Samsung', family: 'SMART_TV', vendor: 'Samsung' },
  { id: 'APPLE_TV', label: 'Apple TV (tvOS)', family: 'APPLE_TV', vendor: 'Apple' },
  { id: 'IOS', label: 'iPhone / iPad (iOS)', family: 'IOS', vendor: 'Apple' }
];

export const APP_SCENARIOS: TestScenario[] = [
  {
    id: 'APP_LAUNCH_LIVE',
    domain: 'APP',
    name: 'Launch + Live TV',
    priority: 1,
    description: 'Open app and start live TV playback from home screen.',
    tags: ['launch', 'live']
  },
  {
    id: 'APP_VOD_PLAYBACK',
    domain: 'APP',
    name: 'VOD Playback',
    priority: 1,
    description: 'Play VOD asset end-to-end with trickplay.',
    tags: ['vod', 'playback']
  },
  {
    id: 'APP_AUTH_FLOW',
    domain: 'APP',
    name: 'Authentication Flow',
    priority: 2,
    description: 'Login with Partner credentials and restore previous session.',
    tags: ['auth', 'login']
  }
];

const APP_VERSIONS_DEFAULT: VersionUnderTest[] = [
  {
    id: 'APP_25_3_303_ANDROID_TV_VSTB',
    domain: 'APP',
    platformId: 'ANDROID_TV_VSTB',
    versionLabel: '25.3.303',
    releaseChannel: 'QA',
    isActive: true
  },
  {
    id: 'APP_25_3_303_STB_SYS_S70PCI',
    domain: 'APP',
    platformId: 'S70PCI_FW',
    versionLabel: '25.3.303',
    releaseChannel: 'QA',
    isActive: true
  }
];

export function loadAppVersions(): VersionUnderTest[] {
  if (typeof window === 'undefined') {
    return [...APP_VERSIONS_DEFAULT];
  }
  try {
    const raw = window.localStorage.getItem(APP_VERSIONS_KEY);
    if (!raw) return [...APP_VERSIONS_DEFAULT];
    const parsed = JSON.parse(raw) as VersionUnderTest[];
    if (!Array.isArray(parsed) || parsed.length === 0) {
      return [...APP_VERSIONS_DEFAULT];
    }
    return parsed;
  } catch {
    return [...APP_VERSIONS_DEFAULT];
  }
}

export function saveAppVersions(versions: VersionUnderTest[]): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(APP_VERSIONS_KEY, JSON.stringify(versions));
  } catch {
    // ignore persistence errors
  }
}

export const APP_TEST_RUNS: TestRunSummary[] = [
  {
    id: 'RUN_APP_ANDROID_TV_VSTB_25_3_303',
    sessionId: 'VS_231125_APP',
    testerId: 'tester-golan-001',
    domain: 'APP',
    platformId: 'ANDROID_TV_VSTB',
    versionId: 'APP_25_3_303_ANDROID_TV_VSTB',
    startedAt: '2025-11-25T10:00:00Z',
    finishedAt: '2025-11-25T10:30:00Z',
    status: 'PASS',
    passRate: 92,
    totalScenarios: 25,
    passedScenarios: 23,
    failedScenarios: 2
  }
];

const APP_ISSUES: TestStepIssue[] = [
  {
    id: 'APP_ISSUE_VOD_STUTTER',
    runId: 'RUN_APP_ANDROID_TV_VSTB_25_3_303',
    scenarioId: 'APP_VOD_PLAYBACK',
    stepIndex: 4,
    title: 'VOD playback stutters after 30 minutes',
    description:
      'On Android TV vSTB, long VOD playback shows stuttering after ~30 minutes of continuous play.',
    suspectedRootCause: 'Buffering / bitrate adaptation issue',
    jiraSummarySuggestion: '[ANDROID_TV_VSTB][APP 25.3.303][VOD] Playback stutters after 30 minutes'
  }
];

export function getLatestAppRunForPlatform(
  platformId: PlatformId,
  dataset: TestRunSummary[] = APP_TEST_RUNS
): TestRunSummary | undefined {
  const runs = dataset.filter((r) => r.platformId === platformId);
  if (runs.length === 0) return undefined;
  return runs.reduce((latest, current) => {
    if (!latest.startedAt) return current;
    if (!current.startedAt) return latest;
    return new Date(current.startedAt) > new Date(latest.startedAt) ? current : latest;
  });
}

export function getAppIssuesForRun(runId: string): TestStepIssue[] {
  return APP_ISSUES.filter((issue) => issue.runId === runId);
}

type AppRunQuery = {
  platformId?: string;
  versionId?: string;
  sessionId?: string;
};

export async function fetchAppPlatformsFromApi(): Promise<Platform[]> {
  try {
    const platforms = await apiGet<Platform[]>('/api/app/platforms');
    return platforms;
  } catch (err) {
    logApiError('fetchAppPlatformsFromApi', err);
    return [...APP_PLATFORMS];
  }
}

export async function fetchAppVersionsFromApi(): Promise<VersionUnderTest[]> {
  try {
    const versions = await apiGet<VersionUnderTest[]>('/api/app/versions');
    return versions;
  } catch (err) {
    logApiError('fetchAppVersionsFromApi', err);
    return loadAppVersions();
  }
}

export async function fetchAppRunsFromApi(query?: AppRunQuery): Promise<TestRunSummary[]> {
  try {
    const params: Record<string, string> = {};
    if (query?.platformId) params.platform_id = query.platformId;
    if (query?.versionId) params.version_id = query.versionId;
    if (query?.sessionId) params.session_id = query.sessionId;
    const runs = await apiGet<TestRunSummary[]>('/api/app/runs', params);
    return runs;
  } catch (err) {
    logApiError('fetchAppRunsFromApi', err);
    return [...APP_TEST_RUNS];
  }
}

export type AppDashboardData = {
  platforms: Platform[];
  versions: VersionUnderTest[];
  runs: TestRunSummary[];
};

export async function loadAppDashboardData(): Promise<AppDashboardData> {
  const [platforms, versions, runs] = await Promise.all([
    fetchAppPlatformsFromApi(),
    fetchAppVersionsFromApi(),
    fetchAppRunsFromApi()
  ]);
  return { platforms, versions, runs };
}

export type {
  Platform,
  VersionUnderTest,
  TestRunSummary,
  TestStepIssue,
  TestScenario
};
