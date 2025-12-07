import type { TvAutoSyncSession, TvAutoSyncTimelineEvent } from '../types/quickset';

export type UiStatus = 'pass' | 'fail' | 'pending';

export interface UiStatusSummary {
  status: UiStatus;
  label: string;
  reasonLines: string[];
  brandMismatch: boolean;
}

export const isAnalyzerResultReady = (session: TvAutoSyncSession): boolean =>
  session.analyzer_ready === true || session.overall_status === 'PASS' || session.overall_status === 'FAIL';

export function deriveUiStatusFromAnalyzer(session: TvAutoSyncSession): UiStatusSummary {
  let status: UiStatus = 'pending';
  const ready = isAnalyzerResultReady(session);

  if (!ready) {
    status = 'pending';
  } else if (session.overall_status === 'PASS' && !session.has_failure) {
    status = 'pass';
  } else {
    status = 'fail';
  }

  const reasonLines: string[] = [];

  if (status === 'pending') {
    reasonLines.push('Analyzer is still running, results are not final yet.');
  } else {
    if (session.brand_mismatch) {
      const userBrand = session.tv_brand_user ?? 'unknown';
      const logBrand = session.tv_brand_log ?? 'unknown';
      reasonLines.push(`Brand mismatch: tester saw "${userBrand}", logs say "${logBrand}".`);
    }

    if (session.has_volume_issue) {
      reasonLines.push('Volume issue detected by analyzer.');
    }

    if (session.has_osd_issue) {
      reasonLines.push('OSD issue detected by analyzer.');
    }

    if (session.analysis_text) {
      reasonLines.push(session.analysis_text);
    }

    if (reasonLines.length === 0 && status === 'pass') {
      reasonLines.push('TV auto-sync flow passed with no detected issues.');
    }
  }

  return {
    status,
    label: status === 'pending' ? 'PENDING' : status === 'pass' ? 'PASS' : 'FAIL',
    reasonLines,
    brandMismatch: ready && session.brand_mismatch === true,
  };
}

const normalizeAnswer = (value?: string | null): string | null => {
  if (typeof value !== 'string') {
    return null;
  }
  const normalized = value.trim().toLowerCase();
  return normalized.length ? normalized : null;
};

const findTimelineAnswer = (
  timeline: TvAutoSyncTimelineEvent[],
  stepName: string
): string | null => {
  const row = timeline.find((event) => event.name === stepName);
  return normalizeAnswer(row?.user_answer ?? null);
};

export type DimensionTileState = 'issue' | 'ok_positive' | 'neutral_not_seen' | 'pending';

export interface DimensionTileResult {
  state: DimensionTileState;
  answer?: string | null;
}

const deriveDimensionTileState = (
  session: TvAutoSyncSession,
  timeline: TvAutoSyncTimelineEvent[],
  stepName: string,
  hasIssue: boolean
): DimensionTileResult => {
  const answer = findTimelineAnswer(timeline, stepName);
  if (hasIssue) {
    return { state: 'issue', answer };
  }
  const ready = isAnalyzerResultReady(session);
  if (!ready) {
    return { state: 'pending', answer };
  }
  if (answer === 'yes') {
    return { state: 'ok_positive', answer };
  }
  if (answer === 'no') {
    return { state: 'neutral_not_seen', answer };
  }
  return { state: 'pending', answer };
};

export const deriveVolumeTileState = (
  session: TvAutoSyncSession,
  timeline: TvAutoSyncTimelineEvent[]
): DimensionTileResult => deriveDimensionTileState(session, timeline, 'question_tv_volume_changed', session.has_volume_issue);

export const deriveOsdTileState = (
  session: TvAutoSyncSession,
  timeline: TvAutoSyncTimelineEvent[]
): DimensionTileResult => deriveDimensionTileState(session, timeline, 'question_tv_osd_seen', session.has_osd_issue);
