import type {
  MetricTriState,
  QuicksetAnalysisDetails,
  TvAutoSyncSession
} from '../types/quickset';
import { isAnalyzerResultReady } from './quicksetStatus';

type AnalyzerMetricFields = Partial<Record<'brand_status' | 'volume_status' | 'osd_status', MetricTriState>>;

interface SessionWithAnalysisResult extends TvAutoSyncSession, AnalyzerMetricFields {
  analysis_result?: (QuicksetAnalysisDetails & AnalyzerMetricFields) | undefined;
}

const normalizeBrandValue = (value: unknown): string | null => {
  if (typeof value !== 'string') {
    return null;
  }
  const trimmed = value.trim();
  return trimmed.length ? trimmed : null;
};

const brandsAreDifferent = (userBrand: string | null, logBrand: string | null): boolean => {
  if (!userBrand || !logBrand) {
    return false;
  }
  return userBrand.toLowerCase() !== logBrand.toLowerCase();
};

export const formatTriStateLabel = (value: MetricTriState): string =>
  value === 'NOT_EVALUATED' ? 'NOT EVALUATED YET' : value;

const isMetricTriState = (value: unknown): value is MetricTriState =>
  value === 'OK' || value === 'FAIL' || value === 'INCOMPATIBILITY' || value === 'NOT_EVALUATED';

const resolveMetricStatus = (
  sessionValue: unknown,
  analysisValue: unknown,
  analyzerReady: boolean,
  fallbackIssue: boolean
): MetricTriState => {
  if (isMetricTriState(sessionValue)) {
    return sessionValue;
  }
  if (isMetricTriState(analysisValue)) {
    return analysisValue;
  }
  if (!analyzerReady) {
    return 'NOT_EVALUATED';
  }
  return fallbackIssue ? 'FAIL' : 'OK';
};

export interface MetricStatusesResult {
  analyzerReady: boolean;
  brandStatus: MetricTriState;
  volumeStatus: MetricTriState;
  osdStatus: MetricTriState;
  preferredUserBrand: string | null;
  preferredLogBrand: string | null;
  hasBrandMismatch: boolean;
}

export const deriveMetricStatuses = (
  session: TvAutoSyncSession,
  analysisDetails?: QuicksetAnalysisDetails
): MetricStatusesResult => {
  const analyzerReady = isAnalyzerResultReady(session);
  const sessionWithMetrics = session as SessionWithAnalysisResult;
  const analysisResultPayload = sessionWithMetrics.analysis_result;

  const payloadFailedSteps = analysisResultPayload?.failed_steps;
  const analysisFailedSteps = analysisDetails?.failed_steps;
  const failedSteps = Array.isArray(payloadFailedSteps)
    ? payloadFailedSteps
    : Array.isArray(analysisFailedSteps)
      ? analysisFailedSteps
      : [];
  const brandStepFailed = failedSteps.includes('question_tv_brand_ui');

  const evidenceFromPayload = analysisResultPayload?.evidence as Record<string, unknown> | undefined;
  const evidenceFromDetails = analysisDetails?.evidence as Record<string, unknown> | undefined;

  const sessionUserBrand = normalizeBrandValue(session.tv_brand_user);
  const sessionLogBrand = normalizeBrandValue(session.tv_brand_log);
  const evidenceUserBrand = normalizeBrandValue(
    evidenceFromPayload?.tv_brand_user ?? evidenceFromDetails?.tv_brand_user
  );
  const evidenceLogBrand = normalizeBrandValue(
    evidenceFromPayload?.tv_brand_detected ??
      evidenceFromPayload?.tv_brand_log ??
      evidenceFromDetails?.tv_brand_detected ??
      evidenceFromDetails?.tv_brand_log
  );

  const preferredUserBrand = sessionUserBrand ?? evidenceUserBrand;
  const preferredLogBrand = sessionLogBrand ?? evidenceLogBrand;
  const hasSessionPairMismatch = brandsAreDifferent(sessionUserBrand, sessionLogBrand);
  const hasDerivedMismatch = !hasSessionPairMismatch && brandsAreDifferent(preferredUserBrand, preferredLogBrand);
  const hasBrandMismatch =
    session.brand_mismatch === true || brandStepFailed || hasSessionPairMismatch || hasDerivedMismatch;

  const brandStatus: MetricTriState = !analyzerReady
    ? 'NOT_EVALUATED'
    : hasBrandMismatch
      ? 'INCOMPATIBILITY'
      : 'OK';

  const volumeStatus = resolveMetricStatus(
    sessionWithMetrics.volume_status,
    analysisResultPayload?.volume_status,
    analyzerReady,
    session.has_volume_issue
  );
  const osdStatus = resolveMetricStatus(
    sessionWithMetrics.osd_status,
    analysisResultPayload?.osd_status,
    analyzerReady,
    session.has_osd_issue
  );

  return {
    analyzerReady,
    brandStatus,
    volumeStatus,
    osdStatus,
    preferredUserBrand,
    preferredLogBrand,
    hasBrandMismatch
  };
};
