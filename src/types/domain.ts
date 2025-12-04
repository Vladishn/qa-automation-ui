// src/types/domain.ts

export type DeviceFamily = 'STB' | 'VSTB' | 'MOBILE' | 'SMART_TV' | 'APPLE_TV' | 'IOS';

export type StbModel = 'S70PCI' | 'JADE' | 'SEI_X4';

export type SmartTvBrand = 'LG' | 'SAMSUNG';

export type PlatformId =
  | 'S70PCI_FW'
  | 'JADE_FW'
  | 'SEI_X4_FW'
  | 'ANDROID_TV_VSTB'
  | 'ANDROID_MOBILE'
  | 'SMART_TV_LG'
  | 'SMART_TV_SAMSUNG'
  | 'APPLE_TV'
  | 'IOS';

export interface Platform {
  id: PlatformId;
  label: string;
  family: DeviceFamily;
  vendor?: string;
  model?: StbModel;
  smartTvBrand?: SmartTvBrand;
}

export type TestDomain = 'FIRMWARE' | 'APP';

export type ScenarioPriority = 1 | 2 | 3 | 4 | 5;

export interface VersionUnderTest {
  id: string;
  domain: TestDomain;
  platformId: PlatformId;
  versionLabel: string;
  buildNumber?: string;
  releaseChannel?: 'DEV' | 'QA' | 'STAGE' | 'PROD';
  /** Optional release date (ISO) – used for version history / sorting */
  releaseDate?: string;
  /** Marks current "active" version for a given platform */
  isActive?: boolean;
}

export interface TestScenario {
  id: string;
  domain: TestDomain;
  name: string;
  description?: string;
  tags?: string[];
  isQuickSetExample?: boolean;
  /** Business priority: 1 (highest) .. 5 (lowest) */
  priority?: ScenarioPriority;
}

export type TestStatus = 'NOT_STARTED' | 'RUNNING' | 'PASS' | 'FAIL' | 'BLOCKED';

export interface TestRunSummary {
  id: string;
  sessionId: string;
  testerId?: string;
  domain: TestDomain;
  platformId: PlatformId;
  versionId: string;
  startedAt: string;
  finishedAt?: string;
  status: TestStatus;
  passRate: number;
  totalScenarios: number;
  passedScenarios: number;
  failedScenarios: number;
}

export interface TestStepIssue {
  id: string;
  scenarioId: string;
  stepIndex: number;
  title: string;
  description: string;
  suspectedRootCause?: string;
  logcatPath?: string;
  adbLogPath?: string;
  screenshotPath?: string;
  jiraSummarySuggestion?: string;
  jiraDescriptionSuggestion?: string;
}

export interface ManagementKpi {
  releaseId: string;
  date: string;
  totalRuns: number;
  overallPassRate: number;
  criticalBugs: number;
  highBugs: number;
  mediumBugs: number;
}

export type QuickSetStepStatus = 'pending' | 'running' | 'pass' | 'fail' | 'inconclusive' | 'info';

export interface QuickSetStep {
  name: string;
  status: QuickSetStepStatus;
  timestamp?: string | null;
  metadata: Record<string, any>;
}

export type QuickSetResult = QuickSetStepStatus | null;

export interface QuickSetQuestion {
  id: string;
  prompt: string;
  step_name: string;
  input_kind: 'continue' | 'boolean' | 'text';
  choices?: string[] | null;
  metadata: Record<string, any>;
}

export interface QuickSetInfraCheck {
  name: string;
  status: 'ok' | 'fail' | 'skip';
  message: string;
}

export interface QuickSetSession {
  session_id: string;
  tester_id: string;
  stb_ip: string;
  scenario_name: string;
  start_time: string;
  end_time?: string | null;
  steps: QuickSetStep[];
  result: QuickSetResult;
  logs: {
    adb: string;
    logcat: string;
  };
  state?: 'running' | 'awaiting_input' | 'completed' | 'failed';
  pending_question?: QuickSetQuestion | null;
  summary?: string | null;
  tv_model?: string | null;
  remote_keys?: string[];
  infra_checks?: QuickSetInfraCheck[];
}

export type TimelineStepStatus = 'INFO' | 'PASS' | 'FAIL' | 'AWAITING_INPUT';

export type OverallStatus = 'PASS' | 'FAIL' | 'AWAITING_INPUT';

export interface TimelineRow {
  name: string;
  label: string;
  status: TimelineStepStatus;
  timestamp?: string | null;
  question?: string | null;
  user_answer?: string | null;
  details?: Record<string, unknown>;
}

export interface SessionSummary {
  session_id: string;
  scenario_name: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  overall_status: OverallStatus;
  brand_mismatch: boolean;
  tv_brand_user?: string | null;
  tv_brand_log?: string | null;
  has_volume_issue: boolean;
  has_osd_issue: boolean;
  notes?: string | null;
  analysis_text: string;
  has_failure: boolean;
}

export interface SessionTimelineResponse {
  session: SessionSummary;
  timeline: TimelineRow[];
  has_failure?: boolean;
}
