// src/services/fwService.ts
// Firmware test data helpers with backend-aware loaders plus local fallbacks.

import { apiGet, logApiError } from './httpClient';
import type {
  Platform,
  PlatformId,
  TestRunSummary,
  TestScenario,
  TestStepIssue,
  VersionUnderTest
} from '../types/domain';

const FW_VERSIONS_KEY = 'fw_versions_v1';

export const FW_PLATFORMS: Platform[] = [
  {
    id: 'S70PCI_FW',
    label: 'S70PCI · Ventiva',
    family: 'STB',
    vendor: 'Ventiva',
    model: 'S70PCI'
  },
  {
    id: 'JADE_FW',
    label: 'Jade · Ventiva',
    family: 'STB',
    vendor: 'Ventiva',
    model: 'JADE'
  },
  {
    id: 'SEI_X4_FW',
    label: 'SEI X4 · SEI',
    family: 'STB',
    vendor: 'SEI',
    model: 'SEI_X4'
  }
];

export const QUICKSET_SCENARIOS: TestScenario[] = [
  {
    id: 'TV_AUTO_SYNC',
    domain: 'FIRMWARE',
    name: 'TV Auto Sync',
    priority: 1,
    description: 'QuickSet auto sync between STB and TV (volume, mute, power).',
    tags: ['quickset', 'volume', 'cec'],
    isQuickSetExample: true
  },
  {
    id: 'REMOTE_PAIR_UNPAIR_FLOW',
    domain: 'FIRMWARE',
    name: 'Remote Pair / Unpair Flow',
    priority: 1,
    description: 'Pair/unpair PartnerRC remote with STB and verify keys.',
    tags: ['remote', 'pairing'],
    isQuickSetExample: true
  },
  {
    id: 'BATTERY_STATUS',
    domain: 'FIRMWARE',
    name: 'Battery Low Status',
    priority: 2,
    description: 'Validate low battery indication for the remote.',
    tags: ['battery', 'remote'],
    isQuickSetExample: false
  }
];

const FW_VERSIONS_DEFAULT: VersionUnderTest[] = [
  {
    id: 'FW_3_4_0_S70PCI',
    domain: 'FIRMWARE',
    platformId: 'S70PCI_FW',
    versionLabel: '3.4.0',
    releaseChannel: 'QA',
    isActive: false
  },
  {
    id: 'FW_3_5_0_S70PCI',
    domain: 'FIRMWARE',
    platformId: 'S70PCI_FW',
    versionLabel: '3.5.0',
    releaseChannel: 'QA',
    isActive: true
  },
  {
    id: 'FW_3_5_0_SEI_X4',
    domain: 'FIRMWARE',
    platformId: 'SEI_X4_FW',
    versionLabel: '3.5.0',
    releaseChannel: 'QA',
    isActive: true
  }
];

export function loadFwVersions(): VersionUnderTest[] {
  if (typeof window === 'undefined') {
    return [...FW_VERSIONS_DEFAULT];
  }

  try {
    const raw = window.localStorage.getItem(FW_VERSIONS_KEY);
    if (!raw) return [...FW_VERSIONS_DEFAULT];
    const parsed = JSON.parse(raw) as VersionUnderTest[];
    if (!Array.isArray(parsed) || parsed.length === 0) {
      return [...FW_VERSIONS_DEFAULT];
    }
    return parsed;
  } catch {
    return [...FW_VERSIONS_DEFAULT];
  }
}

export function saveFwVersions(versions: VersionUnderTest[]): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(FW_VERSIONS_KEY, JSON.stringify(versions));
  } catch {
    // ignore persistence errors
  }
}

export const FW_TEST_RUNS: TestRunSummary[] = [
  {
    id: 'RUN_VS_231125_SEI_X4_FW_3_5_0',
    sessionId: 'VS_231125_E2E',
    testerId: 'tester-golan-001',
    domain: 'FIRMWARE',
    platformId: 'SEI_X4_FW',
    versionId: 'FW_3_5_0_SEI_X4',
    startedAt: '2025-11-25T09:00:00Z',
    finishedAt: '2025-11-25T09:45:00Z',
    status: 'PASS',
    passRate: 95,
    totalScenarios: 20,
    passedScenarios: 19,
    failedScenarios: 1
  },
  {
    id: 'RUN_VS_231120_S70PCI_FW_3_5_0',
    sessionId: 'VS_231120_SMOKE',
    testerId: 'tester-qa-001',
    domain: 'FIRMWARE',
    platformId: 'S70PCI_FW',
    versionId: 'FW_3_5_0_S70PCI',
    startedAt: '2025-11-20T09:00:00Z',
    finishedAt: '2025-11-20T09:25:00Z',
    status: 'PASS',
    passRate: 92,
    totalScenarios: 18,
    passedScenarios: 17,
    failedScenarios: 1
  }
];

const FW_ISSUES: TestStepIssue[] = [
  {
    id: 'ISSUE_SEI_X4_OSD',
    scenarioId: 'TV_AUTO_SYNC',
    stepIndex: 3,
    runId: 'RUN_VS_231125_SEI_X4_FW_3_5_0',
    title: 'Volume OSD from STB instead of TV',
    description:
      'During auto-sync, volume changes show OSD from STB UI instead of TV OSD, indicating CEC mapping problem.',
    suspectedRootCause: 'QuickSet HDMI-CEC mapping still points to STB overlay.',
    jiraSummarySuggestion: '[SEI_X4][FW 3.5.0][TV_AUTO_SYNC] Volume OSD from STB instead of TV'
  }
];

export function getLatestRunForPlatform(
  platformId: PlatformId,
  dataset: TestRunSummary[] = FW_TEST_RUNS
): TestRunSummary | undefined {
  const runs = dataset.filter((r) => r.platformId === platformId);
  if (runs.length === 0) return undefined;
  return runs.reduce((latest, current) => {
    if (!latest.startedAt) return current;
    if (!current.startedAt) return latest;
    return new Date(current.startedAt) > new Date(latest.startedAt) ? current : latest;
  });
}

export function getIssuesForRun(runId: string): TestStepIssue[] {
  return FW_ISSUES.filter((issue) => issue.runId === runId);
}

type RunQuery = {
  platformId?: string;
  versionId?: string;
  sessionId?: string;
};

export async function fetchFwPlatformsFromApi(): Promise<Platform[]> {
  try {
    const platforms = await apiGet<Platform[]>('/api/fw/platforms');
    return platforms;
  } catch (err) {
    logApiError('fetchFwPlatformsFromApi', err);
    return [...FW_PLATFORMS];
  }
}

export async function fetchFwVersionsFromApi(): Promise<VersionUnderTest[]> {
  try {
    const versions = await apiGet<VersionUnderTest[]>('/api/fw/versions');
    return versions;
  } catch (err) {
    logApiError('fetchFwVersionsFromApi', err);
    return loadFwVersions();
  }
}

export async function fetchFwRunsFromApi(query?: RunQuery): Promise<TestRunSummary[]> {
  try {
    const params: Record<string, string> = {};
    if (query?.platformId) params.platform_id = query.platformId;
    if (query?.versionId) params.version_id = query.versionId;
    if (query?.sessionId) params.session_id = query.sessionId;
    const runs = await apiGet<TestRunSummary[]>('/api/fw/runs', params);
    return runs;
  } catch (err) {
    logApiError('fetchFwRunsFromApi', err);
    return [...FW_TEST_RUNS];
  }
}

export type FirmwareDashboardData = {
  platforms: Platform[];
  versions: VersionUnderTest[];
  runs: TestRunSummary[];
};

export async function loadFirmwareDashboardData(): Promise<FirmwareDashboardData> {
  const [platforms, versions, runs] = await Promise.all([
    fetchFwPlatformsFromApi(),
    fetchFwVersionsFromApi(),
    fetchFwRunsFromApi()
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
