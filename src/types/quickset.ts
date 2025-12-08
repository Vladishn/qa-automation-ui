import type { QuickSetSession } from './domain';

export type AnalyzerStepStatus = 'INFO' | 'PASS' | 'FAIL' | 'AWAITING_INPUT' | 'PENDING';
export type MetricTriState = 'OK' | 'FAIL' | 'INCOMPATIBILITY' | 'NOT_EVALUATED';

export interface FailureInsight {
  code: string;
  category: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  title: string;
  description: string;
  evidence_keys?: string[];
}

export interface QuicksetAnalysisDetails {
  analysis: string;
  failed_steps?: string[];
  awaiting_steps?: string[];
  failure_insights?: FailureInsight[];
  evidence?: Record<string, unknown>;
  recommendations?: string[];
  confidence?: 'low' | 'medium' | 'high';
  tester_verdict?: string;
  log_verdict?: string;
  telemetry_state?: string;
  conflict_tester_vs_logs?: boolean;
  log_failure_reason?: string | null;
  autosync_started?: boolean;
  autosync_success?: boolean;
  [key: string]: unknown;
}

export interface TvAutoSyncSession {
  session_id: string;
  scenario_name: string;
  started_at?: string | null;
  finished_at?: string | null;
  overall_status: AnalyzerStepStatus;
  has_failure: boolean;
  brand_mismatch: boolean;
  tv_brand_user?: string | null;
  tv_brand_log?: string | null;
  has_volume_issue: boolean;
  has_osd_issue: boolean;
  brand_status?: MetricTriState;
  volume_status?: MetricTriState;
  osd_status?: MetricTriState;
  analysis_text?: string | null;
  notes?: string | null;
  analyzer_ready?: boolean;
  [key: string]: unknown;
}

export interface TvAutoSyncTimelineEvent {
  name: string;
  label?: string;
  status: AnalyzerStepStatus;
  timestamp?: string | null;
  question?: string | null;
  user_answer?: string | null;
  details: Record<string, unknown>;
}

export interface TvAutoSyncSessionResponse {
  session: TvAutoSyncSession;
  timeline: TvAutoSyncTimelineEvent[];
  has_failure: boolean;
  quickset_session?: QuickSetSession | null;
}
