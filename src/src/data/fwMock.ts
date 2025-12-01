// src/data/fwMock.ts
import type {
  Platform,
  VersionUnderTest,
  TestScenario,
  TestRunSummary
} from '../types/domain';

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

export const FW_VERSIONS: VersionUnderTest[] = [
  {
    id: 'FW_3.0.0_S70PCI',
    domain: 'FIRMWARE',
    platformId: 'S70PCI_FW',
    versionLabel: '3.0.0',
    releaseChannel: 'QA'
  },
  {
    id: 'FW_2.5.1_JADE',
    domain: 'FIRMWARE',
    platformId: 'JADE_FW',
    versionLabel: '2.5.1',
    releaseChannel: 'QA'
  },
  {
    id: 'FW_3.1.0_SEI_X4',
    domain: 'FIRMWARE',
    platformId: 'SEI_X4_FW',
    versionLabel: '3.1.0',
    releaseChannel: 'QA'
  }
];

export const QUICKSET_SCENARIOS: TestScenario[] = [
  {
    id: 'TV_AUTO_SYNC',
    domain: 'FIRMWARE',
    name: 'TV Auto Sync',
    description:
      'Automatic TV brand detection and volume OSD sync using QuickSet on the STB.',
    tags: ['quickset', 'pairing', 'volume'],
    isQuickSetExample: true
  },
  {
    id: 'REMOTE_PAIR_UNPAIR_FLOW',
    domain: 'FIRMWARE',
    name: 'Remote Pair / Unpair',
    description:
      'Pair, unpair and re-pair the PartnerRC remote with the STB, including connectRC and RC_Reboot flows.',
    tags: ['quickset', 'remote', 'pairing'],
    isQuickSetExample: true
  },
  {
    id: 'BATTERY_STATUS',
    domain: 'FIRMWARE',
    name: 'Battery Status',
    description:
      'Low battery indication flow for the remote, including OSD and QuickSet telemetry validation.',
    tags: ['quickset', 'battery'],
    isQuickSetExample: true
  }
];

export const FW_TEST_RUNS: TestRunSummary[] = [
  {
    id: 'RUN_VS_231125_SEI_X4_1',
    sessionId: 'VS_231125',
    testerId: 'tester-golan-001',
    domain: 'FIRMWARE',
    platformId: 'SEI_X4_FW',
    versionId: 'FW_3.1.0_SEI_X4',
    startedAt: '2025-11-24T08:15:00Z',
    finishedAt: '2025-11-24T08:45:00Z',
    status: 'PASS',
    passRate: 95,
    totalScenarios: 4,
    passedScenarios: 3,
    failedScenarios: 1
  },
  {
    id: 'RUN_VS_TEST_002_SEI_X4_TV_AUTO_SYNC',
    sessionId: 'VS_TEST_002',
    testerId: 'tester-vladi-001',
    domain: 'FIRMWARE',
    platformId: 'SEI_X4_FW',
    versionId: 'FW_3.1.0_SEI_X4',
    startedAt: '2025-11-28T10:30:00Z',
    finishedAt: '2025-11-28T10:42:00Z',
    status: 'PASS',
    passRate: 100,
    totalScenarios: 1,
    passedScenarios: 1,
    failedScenarios: 0
  },
  {
    id: 'RUN_S70PCI_SMOKE',
    sessionId: 'VS_S70PCI_SMOKE',
    testerId: 'tester-qa-001',
    domain: 'FIRMWARE',
    platformId: 'S70PCI_FW',
    versionId: 'FW_3.0.0_S70PCI',
    startedAt: '2025-11-20T09:00:00Z',
    finishedAt: '2025-11-20T09:25:00Z',
    status: 'PASS',
    passRate: 92,
    totalScenarios: 5,
    passedScenarios: 4,
    failedScenarios: 1
  },
  {
    id: 'RUN_JADE_REGRESSION',
    sessionId: 'VS_JADE_REG_01',
    testerId: 'tester-qa-002',
    domain: 'FIRMWARE',
    platformId: 'JADE_FW',
    versionId: 'FW_2.5.1_JADE',
    startedAt: '2025-11-21T13:10:00Z',
    finishedAt: '2025-11-21T14:05:00Z',
    status: 'FAIL',
    passRate: 70,
    totalScenarios: 10,
    passedScenarios: 7,
    failedScenarios: 3
  }
];

export function getLatestRunForPlatform(platformId: string): TestRunSummary | undefined {
  const runs = FW_TEST_RUNS.filter((r) => r.platformId === platformId);
  if (runs.length === 0) return undefined;
  // simplistic latest by finishedAt
  return runs
    .slice()
    .sort((a, b) => (a.finishedAt || '').localeCompare(b.finishedAt || ''))
    .pop();
}
