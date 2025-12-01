// src/data/appMock.ts
import type {
  Platform,
  VersionUnderTest,
  TestScenario,
  TestRunSummary,
  TestStepIssue
} from '../types/domain';

// Application platforms
export const APP_PLATFORMS: Platform[] = [
  {
    id: 'S70PCI_FW',
    label: 'STB Sys App · S70PCI',
    family: 'STB',
    vendor: 'Ventiva',
    model: 'S70PCI'
  },
  {
    id: 'JADE_FW',
    label: 'STB Sys App · Jade',
    family: 'STB',
    vendor: 'Ventiva',
    model: 'JADE'
  },
  {
    id: 'SEI_X4_FW',
    label: 'STB Sys App · SEI X4',
    family: 'STB',
    vendor: 'SEI',
    model: 'SEI_X4'
  },
  {
    id: 'ANDROID_TV_VSTB',
    label: 'Android TV · vSTB',
    family: 'VSTB',
    vendor: 'Google'
  },
  {
    id: 'ANDROID_MOBILE',
    label: 'Android Mobile',
    family: 'MOBILE',
    vendor: 'Google'
  },
  {
    id: 'SMART_TV_LG',
    label: 'Smart TV · LG',
    family: 'SMART_TV',
    vendor: 'LG',
    smartTvBrand: 'LG'
  },
  {
    id: 'SMART_TV_SAMSUNG',
    label: 'Smart TV · Samsung',
    family: 'SMART_TV',
    vendor: 'Samsung',
    smartTvBrand: 'SAMSUNG'
  },
  {
    id: 'APPLE_TV',
    label: 'Apple TV (tvOS)',
    family: 'APPLE_TV',
    vendor: 'Apple'
  },
  {
    id: 'IOS',
    label: 'iPhone / iPad (iOS)',
    family: 'IOS',
    vendor: 'Apple'
  }
];

// Application versions per platform (עם היסטוריה בסיסית)
export const APP_VERSIONS: VersionUnderTest[] = [
  // STB Sys App
  {
    id: 'APP_25.3.200_STB_SYS_S70PCI',
    domain: 'APP',
    platformId: 'S70PCI_FW',
    versionLabel: '25.3.200',
    releaseChannel: 'QA',
    releaseDate: '2025-10-01'
  },
  {
    id: 'APP_25.3.303_STB_SYS_S70PCI',
    domain: 'APP',
    platformId: 'S70PCI_FW',
    versionLabel: '25.3.303',
    releaseChannel: 'QA',
    releaseDate: '2025-11-05',
    isActive: true
  },
  {
    id: 'APP_25.3.200_STB_SYS_JADE',
    domain: 'APP',
    platformId: 'JADE_FW',
    versionLabel: '25.3.200',
    releaseChannel: 'QA',
    releaseDate: '2025-10-01'
  },
  {
    id: 'APP_25.3.303_STB_SYS_JADE',
    domain: 'APP',
    platformId: 'JADE_FW',
    versionLabel: '25.3.303',
    releaseChannel: 'QA',
    releaseDate: '2025-11-05',
    isActive: true
  },
  {
    id: 'APP_25.3.200_STB_SYS_SEI_X4',
    domain: 'APP',
    platformId: 'SEI_X4_FW',
    versionLabel: '25.3.200',
    releaseChannel: 'QA',
    releaseDate: '2025-10-01'
  },
  {
    id: 'APP_25.3.303_STB_SYS_SEI_X4',
    domain: 'APP',
    platformId: 'SEI_X4_FW',
    versionLabel: '25.3.303',
    releaseChannel: 'QA',
    releaseDate: '2025-11-05',
    isActive: true
  },

  // Android TV vSTB
  {
    id: 'APP_25.3.200_ANDROID_TV_VSTB',
    domain: 'APP',
    platformId: 'ANDROID_TV_VSTB',
    versionLabel: '25.3.200',
    releaseChannel: 'QA',
    releaseDate: '2025-10-10'
  },
  {
    id: 'APP_25.3.303_ANDROID_TV_VSTB',
    domain: 'APP',
    platformId: 'ANDROID_TV_VSTB',
    versionLabel: '25.3.303',
    releaseChannel: 'QA',
    releaseDate: '2025-11-10',
    isActive: true
  },

  // Android Mobile
  {
    id: 'APP_25.3.200_ANDROID_MOBILE',
    domain: 'APP',
    platformId: 'ANDROID_MOBILE',
    versionLabel: '25.3.200',
    releaseChannel: 'QA',
    releaseDate: '2025-10-12'
  },
  {
    id: 'APP_25.3.303_ANDROID_MOBILE',
    domain: 'APP',
    platformId: 'ANDROID_MOBILE',
    versionLabel: '25.3.303',
    releaseChannel: 'QA',
    releaseDate: '2025-11-12',
    isActive: true
  },

  // Smart TV
  {
    id: 'APP_25.3.200_SMART_TV_LG',
    domain: 'APP',
    platformId: 'SMART_TV_LG',
    versionLabel: '25.3.200',
    releaseChannel: 'QA',
    releaseDate: '2025-10-15'
  },
  {
    id: 'APP_25.3.303_SMART_TV_LG',
    domain: 'APP',
    platformId: 'SMART_TV_LG',
    versionLabel: '25.3.303',
    releaseChannel: 'QA',
    releaseDate: '2025-11-15',
    isActive: true
  },
  {
    id: 'APP_25.3.200_SMART_TV_SAMSUNG',
    domain: 'APP',
    platformId: 'SMART_TV_SAMSUNG',
    versionLabel: '25.3.200',
    releaseChannel: 'QA',
    releaseDate: '2025-10-15'
  },
  {
    id: 'APP_25.3.303_SMART_TV_SAMSUNG',
    domain: 'APP',
    platformId: 'SMART_TV_SAMSUNG',
    versionLabel: '25.3.303',
    releaseChannel: 'QA',
    releaseDate: '2025-11-15',
    isActive: true
  },

  // Apple TV
  {
    id: 'APP_25.3.200_APPLE_TV',
    domain: 'APP',
    platformId: 'APPLE_TV',
    versionLabel: '25.3.200',
    releaseChannel: 'QA',
    releaseDate: '2025-10-20'
  },
  {
    id: 'APP_25.3.303_APPLE_TV',
    domain: 'APP',
    platformId: 'APPLE_TV',
    versionLabel: '25.3.303',
    releaseChannel: 'QA',
    releaseDate: '2025-11-20',
    isActive: true
  },

  // iOS
  {
    id: 'APP_25.3.200_IOS',
    domain: 'APP',
    platformId: 'IOS',
    versionLabel: '25.3.200',
    releaseChannel: 'QA',
    releaseDate: '2025-10-22'
  },
  {
    id: 'APP_25.3.303_IOS',
    domain: 'APP',
    platformId: 'IOS',
    versionLabel: '25.3.303',
    releaseChannel: 'QA',
    releaseDate: '2025-11-22',
    isActive: true
  }
];

// App test scenarios – high-level flows with priority
export const APP_SCENARIOS: TestScenario[] = [
  {
    id: 'LOGIN',
    domain: 'APP',
    name: 'Login & Authentication',
    description: 'User login with Partner credentials, token refresh and session handling.',
    tags: ['auth', 'backend'],
    priority: 1
  },
  {
    id: 'LIVE_ZAP',
    domain: 'APP',
    name: 'Live TV Zap',
    description: 'Channel zap between multiple live channels with EPG sync.',
    tags: ['live', 'zap', 'epg'],
    priority: 1
  },
  {
    id: 'VOD_PLAYBACK',
    domain: 'APP',
    name: 'VOD Playback',
    description: 'Start, pause, resume and seek VOD asset, with trickplay controls.',
    tags: ['vod', 'playback'],
    priority: 2
  },
  {
    id: 'TIMESHIFT',
    domain: 'APP',
    name: 'Timeshift / Pause Live',
    description: 'Pause live TV, scrub back, resume, and return to live.',
    tags: ['live', 'timeshift'],
    priority: 2
  },
  {
    id: 'SEARCH',
    domain: 'APP',
    name: 'Search & Discovery',
    description: 'Search for content by title/actor/genre and navigate to details.',
    tags: ['search', 'discovery'],
    priority: 3
  }
];

// Example app test runs
export const APP_TEST_RUNS: TestRunSummary[] = [
  {
    id: 'APP_RUN_STB_SYS_SEI_X4_01',
    sessionId: 'APP_SEI_X4_SYS_01',
    testerId: 'tester-vladi-001',
    domain: 'APP',
    platformId: 'SEI_X4_FW',
    versionId: 'APP_25.3.303_STB_SYS_SEI_X4',
    startedAt: '2025-11-27T08:00:00Z',
    finishedAt: '2025-11-27T08:40:00Z',
    status: 'PASS',
    passRate: 96,
    totalScenarios: 5,
    passedScenarios: 5,
    failedScenarios: 0
  },
  {
    id: 'APP_RUN_ANDROID_TV_VSTB_00',
    sessionId: 'APP_ANDROID_TV_00',
    testerId: 'tester-qa-android-001',
    domain: 'APP',
    platformId: 'ANDROID_TV_VSTB',
    versionId: 'APP_25.3.200_ANDROID_TV_VSTB',
    startedAt: '2025-10-26T10:15:00Z',
    finishedAt: '2025-10-26T10:50:00Z',
    status: 'PASS',
    passRate: 90,
    totalScenarios: 5,
    passedScenarios: 4,
    failedScenarios: 1
  },
  {
    id: 'APP_RUN_ANDROID_TV_VSTB_01',
    sessionId: 'APP_ANDROID_TV_01',
    testerId: 'tester-qa-android-001',
    domain: 'APP',
    platformId: 'ANDROID_TV_VSTB',
    versionId: 'APP_25.3.303_ANDROID_TV_VSTB',
    startedAt: '2025-11-26T10:15:00Z',
    finishedAt: '2025-11-26T11:00:00Z',
    status: 'FAIL',
    passRate: 80,
    totalScenarios: 5,
    passedScenarios: 4,
    failedScenarios: 1
  },
  {
    id: 'APP_RUN_ANDROID_MOBILE_01',
    sessionId: 'APP_ANDROID_MOBILE_01',
    testerId: 'tester-qa-mobile-001',
    domain: 'APP',
    platformId: 'ANDROID_MOBILE',
    versionId: 'APP_25.3.303_ANDROID_MOBILE',
    startedAt: '2025-11-25T09:00:00Z',
    finishedAt: '2025-11-25T09:35:00Z',
    status: 'PASS',
    passRate: 100,
    totalScenarios: 4,
    passedScenarios: 4,
    failedScenarios: 0
  },
  {
    id: 'APP_RUN_SMART_TV_LG_01',
    sessionId: 'APP_SMART_TV_LG_01',
    testerId: 'tester-lg-001',
    domain: 'APP',
    platformId: 'SMART_TV_LG',
    versionId: 'APP_25.3.303_SMART_TV_LG',
    startedAt: '2025-11-24T14:00:00Z',
    finishedAt: '2025-11-24T14:50:00Z',
    status: 'FAIL',
    passRate: 75,
    totalScenarios: 4,
    passedScenarios: 3,
    failedScenarios: 1
  },
  {
    id: 'APP_RUN_SMART_TV_SAMSUNG_01',
    sessionId: 'APP_SMART_TV_SAMSUNG_01',
    testerId: 'tester-samsung-001',
    domain: 'APP',
    platformId: 'SMART_TV_SAMSUNG',
    versionId: 'APP_25.3.303_SMART_TV_SAMSUNG',
    startedAt: '2025-11-24T15:10:00Z',
    finishedAt: '2025-11-24T15:55:00Z',
    status: 'PASS',
    passRate: 90,
    totalScenarios: 4,
    passedScenarios: 4,
    failedScenarios: 0
  },
  {
    id: 'APP_RUN_APPLE_TV_01',
    sessionId: 'APP_APPLE_TV_01',
    testerId: 'tester-apple-001',
    domain: 'APP',
    platformId: 'APPLE_TV',
    versionId: 'APP_25.3.303_APPLE_TV',
    startedAt: '2025-11-23T11:00:00Z',
    finishedAt: '2025-11-23T11:40:00Z',
    status: 'PASS',
    passRate: 100,
    totalScenarios: 3,
    passedScenarios: 3,
    failedScenarios: 0
  },
  {
    id: 'APP_RUN_IOS_01',
    sessionId: 'APP_IOS_01',
    testerId: 'tester-ios-001',
    domain: 'APP',
    platformId: 'IOS',
    versionId: 'APP_25.3.303_IOS',
    startedAt: '2025-11-22T16:00:00Z',
    finishedAt: '2025-11-22T16:30:00Z',
    status: 'PASS',
    passRate: 100,
    totalScenarios: 3,
    passedScenarios: 3,
    failedScenarios: 0
  }
];

export function getLatestAppRunForPlatform(platformId: string): TestRunSummary | undefined {
  const runs = APP_TEST_RUNS.filter((r) => r.platformId === platformId);
  if (runs.length === 0) return undefined;
  return runs
    .slice()
    .sort((a, b) => (a.finishedAt || '').localeCompare(b.finishedAt || ''))
    .pop();
}

/**
 * Example issues per app run (to drive Session Details + Jira text).
 * Key: TestRunSummary.id
 */
export const APP_ISSUES_BY_RUN: Record<string, TestStepIssue[]> = {
  APP_RUN_ANDROID_TV_VSTB_01: [
    {
      id: 'ISSUE_ANDROID_TV_VOD_FREEZE',
      scenarioId: 'VOD_PLAYBACK',
      stepIndex: 4,
      title: 'VOD playback freezes after seek',
      description:
        'On Android TV vSTB, app version 25.3.303, performing a seek forward during VOD playback causes video to freeze while audio continues for ~5 seconds, then both stop.',
      suspectedRootCause:
        'Player pipeline not handling seek complete event correctly; potential race between DASH buffer and UI state.',
      jiraSummarySuggestion:
        '[Android TV vSTB][VOD_PLAYBACK] Video freeze after seek forward',
      jiraDescriptionSuggestion:
        'Environment:\n- Platform: Android TV vSTB\n- App: 25.3.303\n- Scenario: VOD_PLAYBACK\n\nSteps:\n1. Launch Partner TV app on Android TV vSTB.\n2. Start playback of any VOD asset.\n3. After ~30 seconds, perform a seek forward (e.g. +10s / scrub forward).\n\nExpected:\n- Playback resumes smoothly from new position with audio and video in sync.\n\nActual:\n- Video freezes while audio continues for ~5 seconds, then both audio and video stop.\n\nImpact:\n- User cannot continue watching VOD without exiting and re-entering playback.\n\nNotes:\n- Issue reproduced several times during regression run APP_ANDROID_TV_01.'
    }
  ],
  APP_RUN_SMART_TV_LG_01: [
    {
      id: 'ISSUE_LG_TIMESHIFT_RETURN_TO_LIVE',
      scenarioId: 'TIMESHIFT',
      stepIndex: 3,
      title: 'Timeshift return-to-live jumps to wrong position',
      description:
        'On Smart TV LG, app version 25.3.303, after pausing live TV for ~2 minutes and then pressing LIVE, playback resumes a few seconds behind true live edge.',
      suspectedRootCause:
        'Incorrect live edge calculation or buffer window handling when resuming from timeshift.',
      jiraSummarySuggestion:
        '[Smart TV LG][TIMESHIFT] Return-to-live resumes behind live edge',
      jiraDescriptionSuggestion:
        'Environment:\n- Platform: Smart TV LG\n- App: 25.3.303\n- Scenario: TIMESHIFT\n\nSteps:\n1. Launch Partner TV app on LG Smart TV.\n2. Watch a live channel.\n3. Press pause and wait ~2 minutes.\n4. Press LIVE / return-to-live.\n\nExpected:\n- Playback jumps to real live edge.\n\nActual:\n- Playback resumes a few seconds behind the real live edge (buffer gap).\n\nImpact:\n- User sees a delayed feed when expecting real live TV.\n\nNotes:\n- Observed repeatedly during APP_SMART_TV_LG_01.'
    }
  ],
  APP_RUN_STB_SYS_SEI_X4_01: [],
  APP_RUN_ANDROID_TV_VSTB_00: [],
  APP_RUN_ANDROID_MOBILE_01: [],
  APP_RUN_SMART_TV_SAMSUNG_01: [],
  APP_RUN_APPLE_TV_01: [],
  APP_RUN_IOS_01: []
};

export function getAppIssuesForRun(runId: string): TestStepIssue[] {
  return APP_ISSUES_BY_RUN[runId] ?? [];
}
