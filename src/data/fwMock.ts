// src/data/fwMock.ts
import type {
  Platform,
  VersionUnderTest,
  TestScenario,
  TestRunSummary,
  TestStepIssue
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
  // S70PCI history
  {
    id: 'FW_2.8.0_S70PCI',
    domain: 'FIRMWARE',
    platformId: 'S70PCI_FW',
    versionLabel: '2.8.0',
    releaseChannel: 'QA',
    releaseDate: '2025-10-01'
  },
  {
    id: 'FW_2.9.0_S70PCI',
    domain: 'FIRMWARE',
    platformId: 'S70PCI_FW',
    versionLabel: '2.9.0',
    releaseChannel: 'QA',
    releaseDate: '2025-10-15'
  },
  {
    id: 'FW_3.0.0_S70PCI',
    domain: 'FIRMWARE',
    platformId: 'S70PCI_FW',
    versionLabel: '3.0.0',
    releaseChannel: 'QA',
    releaseDate: '2025-11-01',
    isActive: true
  },

  // Jade history
  {
    id: 'FW_2.4.0_JADE',
    domain: 'FIRMWARE',
    platformId: 'JADE_FW',
    versionLabel: '2.4.0',
    releaseChannel: 'QA',
    releaseDate: '2025-09-20'
  },
  {
    id: 'FW_2.5.0_JADE',
    domain: 'FIRMWARE',
    platformId: 'JADE_FW',
    versionLabel: '2.5.0',
    releaseChannel: 'QA',
    releaseDate: '2025-10-10'
  },
  {
    id: 'FW_2.5.1_JADE',
    domain: 'FIRMWARE',
    platformId: 'JADE_FW',
    versionLabel: '2.5.1',
    releaseChannel: 'QA',
    releaseDate: '2025-11-05',
    isActive: true
  },

  // SEI X4 history
  {
    id: 'FW_2.9.5_SEI_X4',
    domain: 'FIRMWARE',
    platformId: 'SEI_X4_FW',
    versionLabel: '2.9.5',
    releaseChannel: 'QA',
    releaseDate: '2025-10-05'
  },
  {
    id: 'FW_3.0.0_SEI_X4',
    domain: 'FIRMWARE',
    platformId: 'SEI_X4_FW',
    versionLabel: '3.0.0',
    releaseChannel: 'QA',
    releaseDate: '2025-10-25'
  },
  {
    id: 'FW_3.1.0_SEI_X4',
    domain: 'FIRMWARE',
    platformId: 'SEI_X4_FW',
    versionLabel: '3.1.0',
    releaseChannel: 'QA',
    releaseDate: '2025-11-10',
    isActive: true
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
    isQuickSetExample: true,
    priority: 1
  },
  {
    id: 'REMOTE_PAIR_UNPAIR_FLOW',
    domain: 'FIRMWARE',
    name: 'Remote Pair / Unpair',
    description:
      'Pair, unpair and re-pair the PartnerRC remote with the STB, including connectRC and RC_Reboot flows.',
    tags: ['quickset', 'remote', 'pairing'],
    isQuickSetExample: true,
    priority: 1
  },
  {
    id: 'BATTERY_STATUS',
    domain: 'FIRMWARE',
    name: 'Battery Status',
    description:
      'Low battery indication flow for the remote, including OSD and QuickSet telemetry validation.',
    tags: ['quickset', 'battery'],
    isQuickSetExample: true,
    priority: 2
  }
];

export const FW_TEST_RUNS: TestRunSummary[] = [
  // SEI X4 – older version with regressions
  {
    id: 'RUN_SEI_X4_2_9_5_TV_AUTO_SYNC',
    sessionId: 'VS_SEI_X4_2_9_5_TV_AUTO_SYNC',
    testerId: 'tester-qa-001',
    domain: 'FIRMWARE',
    platformId: 'SEI_X4_FW',
    versionId: 'FW_2.9.5_SEI_X4',
    startedAt: '2025-10-06T08:10:00Z',
    finishedAt: '2025-10-06T08:25:00Z',
    status: 'FAIL',
    passRate: 75,
    totalScenarios: 4,
    passedScenarios: 3,
    failedScenarios: 1
  },
  {
    id: 'RUN_SEI_X4_3_0_0_TV_AUTO_SYNC',
    sessionId: 'VS_SEI_X4_3_0_0_TV_AUTO_SYNC',
    testerId: 'tester-qa-002',
    domain: 'FIRMWARE',
    platformId: 'SEI_X4_FW',
    versionId: 'FW_3.0.0_SEI_X4',
    startedAt: '2025-10-26T09:00:00Z',
    finishedAt: '2025-10-26T09:20:00Z',
    status: 'FAIL',
    passRate: 80,
    totalScenarios: 4,
    passedScenarios: 3,
    failedScenarios: 1
  },
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

  // S70PCI
  {
    id: 'RUN_S70PCI_2_9_0_SMOKE',
    sessionId: 'VS_S70PCI_2_9_0_SMOKE',
    testerId: 'tester-qa-001',
    domain: 'FIRMWARE',
    platformId: 'S70PCI_FW',
    versionId: 'FW_2.9.0_S70PCI',
    startedAt: '2025-10-16T09:00:00Z',
    finishedAt: '2025-10-16T09:20:00Z',
    status: 'PASS',
    passRate: 88,
    totalScenarios: 5,
    passedScenarios: 4,
    failedScenarios: 1
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

  // Jade
  {
    id: 'RUN_JADE_2_5_0_REGRESSION',
    sessionId: 'VS_JADE_REG_00',
    testerId: 'tester-qa-002',
    domain: 'FIRMWARE',
    platformId: 'JADE_FW',
    versionId: 'FW_2.5.0_JADE',
    startedAt: '2025-10-11T13:10:00Z',
    finishedAt: '2025-10-11T13:50:00Z',
    status: 'PASS',
    passRate: 85,
    totalScenarios: 10,
    passedScenarios: 8,
    failedScenarios: 2
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
  return runs
    .slice()
    .sort((a, b) => (a.finishedAt || '').localeCompare(b.finishedAt || ''))
    .pop();
}

/**
 * Example issues per run, to drive "Session Details" and Jira-ready text.
 * Key: TestRunSummary.id
 */
export const FW_ISSUES_BY_RUN: Record<string, TestStepIssue[]> = {
  RUN_SEI_X4_2_9_5_TV_AUTO_SYNC: [
    {
      id: 'ISSUE_SEI_X4_TV_AUTO_SYNC_FAIL_2_9_5',
      scenarioId: 'TV_AUTO_SYNC',
      stepIndex: 3,
      title: 'TV_AUTO_SYNC fails to detect brand',
      description:
        'On SEI X4 FW 2.9.5, TV_AUTO_SYNC does not detect Samsung TV brand; flow ends with generic failure screen.',
      suspectedRootCause: 'QuickSet brand database not updated / mapping missing for this TV model.',
      jiraSummarySuggestion:
        '[SEI X4 FW 2.9.5][QuickSet][TV_AUTO_SYNC] Brand detection fails for Samsung TV',
      jiraDescriptionSuggestion:
        'Environment:\n- STB: SEI X4\n- FW: 2.9.5\n- Scenario: TV_AUTO_SYNC\n\nSteps:\n1. Run QuickSet TV_AUTO_SYNC on SEI X4.\n2. Follow on-screen instructions until brand detection step.\n\nExpected:\n- Samsung TV is detected and pairing flow continues.\n\nActual:\n- Flow ends with generic failure, no brand is detected.\n\nImpact:\n- User cannot auto-sync TV control for this setup.'
    }
  ],
  RUN_SEI_X4_3_0_0_TV_AUTO_SYNC: [
    {
      id: 'ISSUE_SEI_X4_OSD_MISMATCH_3_0_0',
      scenarioId: 'TV_AUTO_SYNC',
      stepIndex: 4,
      title: 'Volume OSD mismatch after successful auto-sync',
      description:
        'On SEI X4 FW 3.0.0, TV_AUTO_SYNC completes but volume change shows OSD from STB instead of TV.',
      suspectedRootCause:
        'QuickSet mapping still using STB volume overlay despite correct TV CEC commands.',
      jiraSummarySuggestion:
        '[SEI X4 FW 3.0.0][QuickSet][TV_AUTO_SYNC] STB OSD displayed instead of TV OSD after sync',
      jiraDescriptionSuggestion:
        'Environment:\n- STB: SEI X4\n- FW: 3.0.0\n- Scenario: TV_AUTO_SYNC\n\nSteps:\n1. Run QuickSet TV_AUTO_SYNC.\n2. Once pairing is successful, change volume using PartnerRC.\n\nExpected:\n- TV volume changes and TV-native OSD is displayed.\n\nActual:\n- Volume changes but OSD is from the STB UI.'
    }
  ],
  RUN_VS_231125_SEI_X4_1: [
    {
      id: 'ISSUE_SEI_X4_VOL_OSD_MISMATCH',
      scenarioId: 'TV_AUTO_SYNC',
      stepIndex: 3,
      title: 'Volume OSD source mismatch',
      description:
        'During TV_AUTO_SYNC on SEI X4 (FW 3.1.0), TV volume changed but OSD source appeared to be from STB instead of the TV. Expected pure TV OSD.',
      suspectedRootCause:
        'QuickSet mapping incorrectly uses STB volume overlay while sending volume CEC to TV.',
      logcatPath: '/logs/sei_x4/VS_231125/logcat.txt',
      adbLogPath: '/logs/sei_x4/VS_231125/adb.txt',
      jiraSummarySuggestion:
        '[SEI X4][QuickSet][TV_AUTO_SYNC] Volume OSD displayed from STB instead of TV',
      jiraDescriptionSuggestion:
        'Environment:\n- STB: SEI X4\n- FW: 3.1.0\n- Scenario: TV_AUTO_SYNC\n\nSteps:\n1. Run QuickSet TV_AUTO_SYNC on SEI X4.\n2. Complete pairing flow.\n3. Change volume using PartnerRC.\n\nExpected:\n- TV volume changes and OSD is shown by TV only.\n\nActual:\n- Volume changes on TV but OSD appears to be from the STB UI.\n\nArtifacts:\n- logcat: /logs/sei_x4/VS_231125/logcat.txt\n- adb: /logs/sei_x4/VS_231125/adb.txt'
    }
  ],
  RUN_VS_TEST_002_SEI_X4_TV_AUTO_SYNC: [],
  RUN_S70PCI_2_9_0_SMOKE: [],
  RUN_S70PCI_SMOKE: [
    {
      id: 'ISSUE_S70PCI_CONNECTRC_REAPPEAR',
      scenarioId: 'REMOTE_PAIR_UNPAIR_FLOW',
      stepIndex: 5,
      title: 'connectRC screen reappears after successful re-pair',
      description:
        'On S70PCI smoke FW 3.0.0, after re-pairing the remote and confirming all keys work, connectRC screen reappears unexpectedly after ~30 seconds of usage.',
      suspectedRootCause:
        'Stale QuickSet state not cleared after successful re-pair; heartbeat reports remote as disconnected.',
      jiraSummarySuggestion:
        '[S70PCI][QuickSet][REMOTE_PAIR_UNPAIR] connectRC screen reappears after successful re-pair',
      jiraDescriptionSuggestion:
        'Environment:\n- STB: S70PCI\n- FW: 3.0.0\n- Scenario: REMOTE_PAIR_UNPAIR_FLOW\n\nSteps:\n1. Unpair remote using QuickSet.\n2. Pair remote again and confirm all keys respond.\n3. Use remote for ~30 seconds.\n\nExpected:\n- Remote remains paired, no reconnect screens.\n\nActual:\n- connectRC screen reappears after short usage window.\n\nArtifacts:\n- N/A (placeholder for future logcat/adb paths).'
    }
  ],
  RUN_JADE_2_5_0_REGRESSION: [],
  RUN_JADE_REGRESSION: [
    {
      id: 'ISSUE_JADE_BATTERY_OSD_MISSING',
      scenarioId: 'BATTERY_STATUS',
      stepIndex: 2,
      title: 'Battery low OSD not displayed',
      description:
        'On Jade FW 2.5.1, low battery simulation for the remote does not trigger battery low OSD on screen.',
      suspectedRootCause:
        'Missing or incorrect subscription to QuickSet battery status notifications in FW.',
      jiraSummarySuggestion:
        '[Jade][QuickSet][BATTERY_STATUS] Low battery OSD not displayed',
      jiraDescriptionSuggestion:
        'Environment:\n- STB: Jade\n- FW: 2.5.1\n- Scenario: BATTERY_STATUS\n\nSteps:\n1. Trigger low battery condition for PartnerRC (simulated/instrumented).\n2. Observe on-screen behavior.\n\nExpected:\n- Battery low OSD is shown on screen.\n\nActual:\n- No battery-related OSD is shown.\n\nArtifacts:\n- N/A (placeholder for future logcat/adb paths).'
    }
  ]
};

export function getIssuesForRun(runId: string): TestStepIssue[] {
  return FW_ISSUES_BY_RUN[runId] ?? [];
}
