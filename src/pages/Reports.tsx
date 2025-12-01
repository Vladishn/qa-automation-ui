// src/pages/Reports.tsx
import React, { useEffect, useMemo, useState } from 'react';
import {
  loadFirmwareDashboardData,
  getIssuesForRun as getFwIssuesForRun,
  QUICKSET_SCENARIOS,
} from '../services/fwService';
import {
  loadAppDashboardData,
  getAppIssuesForRun,
  APP_SCENARIOS,
} from '../services/appService';
import type {
  Platform,
  TestRunSummary,
  TestStepIssue,
  VersionUnderTest,
} from '../types/domain';

type DomainKind = 'FW' | 'APP';

type RunWithDomain = TestRunSummary & {
  domainKind: DomainKind;
  platformLabel: string;
  versionLabel: string;
};

type ScenarioAggRow = {
  domainKind: DomainKind;
  scenarioId: string;
  occurrences: number;
  affectedPlatforms: number;
  firstVersion?: string;
  latestVersion?: string;
};

type DatasetState = {
  platforms: Platform[];
  versions: VersionUnderTest[];
  runs: TestRunSummary[];
};

const emptyDataset: DatasetState = {
  platforms: [],
  versions: [],
  runs: [],
};

type HeatmapStatus = 'NOT_RUN' | 'PASS' | 'FAIL' | 'RECOVERED';

type HeatmapCell = {
  scenarioId: string;
  status: HeatmapStatus;
};

type HeatmapRow = {
  platformId: string;
  platformLabel: string;
  cells: HeatmapCell[];
};

const statusToClass: Record<HeatmapStatus, string> = {
  NOT_RUN: 'heatmap-cell--notrun',
  PASS: 'heatmap-cell--pass',
  FAIL: 'heatmap-cell--fail',
  RECOVERED: 'heatmap-cell--recovered',
};

const statusToLabel: Record<HeatmapStatus, string> = {
  NOT_RUN: '–',
  PASS: 'Pass',
  FAIL: 'Fail',
  RECOVERED: 'Recovered',
};

function buildHeatmapRows(
  dataset: DatasetState,
  scenarios: { id: string; name: string }[],
  getIssuesForRun: (runId: string) => TestStepIssue[],
): HeatmapRow[] {
  if (!dataset.platforms.length || !dataset.runs.length) {
    return [];
  }

  // קבוצת ריצות לפי פלטפורמה
  const runsByPlatform = new Map<string, TestRunSummary[]>();
  const issuesByRunId = new Map<string, TestStepIssue[]>();

  dataset.runs.forEach((run) => {
    const arr = runsByPlatform.get(run.platformId) ?? [];
    arr.push(run);
    runsByPlatform.set(run.platformId, arr);

    const issues = getIssuesForRun(run.id) ?? [];
    issuesByRunId.set(run.id, issues);
  });

  const rows: HeatmapRow[] = [];

  dataset.platforms.forEach((platform) => {
    const platformRuns = (runsByPlatform.get(platform.id) ?? []).slice();
    if (platformRuns.length > 1) {
      platformRuns.sort((a, b) =>
        (a.startedAt ?? '').localeCompare(b.startedAt ?? ''),
      );
    }
    const latestRun =
      platformRuns.length > 0
        ? platformRuns[platformRuns.length - 1]
        : undefined;

    const cells: HeatmapCell[] = scenarios.map((scenario) => {
      if (!platformRuns.length) {
        return {
          scenarioId: scenario.id,
          status: 'NOT_RUN',
        };
      }

      let hadIssueEver = false;
      let latestHasIssue = false;

      platformRuns.forEach((run) => {
        const issues = issuesByRunId.get(run.id) ?? [];
        const hasForScenario = issues.some(
          (i) => i.scenarioId === scenario.id,
        );
        if (hasForScenario) {
          hadIssueEver = true;
          if (latestRun && run.id === latestRun.id) {
            latestHasIssue = true;
          }
        }
      });

      let status: HeatmapStatus;
      if (!hadIssueEver) {
        status = 'PASS';
      } else if (latestHasIssue) {
        status = 'FAIL';
      } else {
        status = 'RECOVERED';
      }

      return {
        scenarioId: scenario.id,
        status,
      };
    });

    rows.push({
      platformId: platform.id,
      platformLabel: platform.label,
      cells,
    });
  });

  return rows;
}

const Reports: React.FC = () => {
  const [fwData, setFwData] = useState<DatasetState>(emptyDataset);
  const [appData, setAppData] = useState<DatasetState>(emptyDataset);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const sync = async () => {
      try {
        setIsLoading(true);
        setLoadError(null);
        const [fw, app] = await Promise.all([
          loadFirmwareDashboardData(),
          loadAppDashboardData(),
        ]);

        if (cancelled) return;

        setFwData({
          platforms: fw.platforms ?? [],
          versions: fw.versions ?? [],
          runs: fw.runs ?? [],
        });

        setAppData({
          platforms: app.platforms ?? [],
          versions: app.versions ?? [],
          runs: app.runs ?? [],
        });
      } catch (err) {
        console.error('[Reports] Failed to load dashboard data', err);
        if (!cancelled) {
          setLoadError(
            'Failed to load aggregated data from backend. Showing whatever is available locally.',
          );
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    void sync();

    return () => {
      cancelled = true;
    };
  }, []);

  // מאחדים את כל ה־runs לשורת זמן אחת (FW + APP)
  const allRuns: RunWithDomain[] = useMemo(() => {
    const fw: RunWithDomain[] = fwData.runs.map((run) => {
      const platform = fwData.platforms.find((p) => p.id === run.platformId);
      const version = fwData.versions.find((v) => v.id === run.versionId);
      return {
        ...run,
        domainKind: 'FW',
        platformLabel: platform?.label ?? run.platformId,
        versionLabel: version?.versionLabel ?? 'N/A',
      };
    });

    const app: RunWithDomain[] = appData.runs.map((run) => {
      const platform = appData.platforms.find((p) => p.id === run.platformId);
      const version = appData.versions.find((v) => v.id === run.versionId);
      return {
        ...run,
        domainKind: 'APP',
        platformLabel: platform?.label ?? run.platformId,
        versionLabel: version?.versionLabel ?? 'N/A',
      };
    });

    return [...fw, ...app].sort((a, b) => {
      const aTime = a.startedAt ?? '';
      const bTime = b.startedAt ?? '';
      return bTime.localeCompare(aTime);
    });
  }, [fwData, appData]);

  // KPIs גלובליים
  const {
    totalRuns,
    totalFwRuns,
    totalAppRuns,
    totalPlatforms,
    globalPassRate,
    totalScenarios,
    totalPassedScenarios,
  } = useMemo(() => {
    const totalRunsLocal = allRuns.length;
    const totalFw = fwData.runs.length;
    const totalApp = appData.runs.length;

    const fwPlatformIds = fwData.platforms.map((p) => p.id);
    const appPlatformIds = appData.platforms.map((p) => p.id);
    const uniquePlatforms = new Set<string>([...fwPlatformIds, ...appPlatformIds]);

    let scenariosTotal = 0;
    let scenariosPassed = 0;

    allRuns.forEach((run) => {
      const total = run.totalScenarios ?? 0;
      const passed = run.passedScenarios ?? 0;
      scenariosTotal += total;
      scenariosPassed += passed;
    });

    const passRate =
      scenariosTotal > 0 ? (scenariosPassed / scenariosTotal) * 100 : null;

    return {
      totalRuns: totalRunsLocal,
      totalFwRuns: totalFw,
      totalAppRuns: totalApp,
      totalPlatforms: uniquePlatforms.size,
      globalPassRate: passRate,
      totalScenarios: scenariosTotal,
      totalPassedScenarios: scenariosPassed,
    };
  }, [allRuns, fwData, appData]);

  // איסוף כל ה־issues (FW + APP)
  const allIssues: { issue: TestStepIssue; domainKind: DomainKind }[] = useMemo(() => {
    const out: { issue: TestStepIssue; domainKind: DomainKind }[] = [];

    fwData.runs.forEach((run) => {
      const issues = getFwIssuesForRun(run.id) ?? [];
      issues.forEach((issue) => out.push({ issue, domainKind: 'FW' }));
    });

    appData.runs.forEach((run) => {
      const issues = getAppIssuesForRun(run.id) ?? [];
      issues.forEach((issue) => out.push({ issue, domainKind: 'APP' }));
    });

    return out;
  }, [fwData, appData]);

  // טופ רגרסיות לפי scenarioId (FW + APP)
  const topScenarioAgg: ScenarioAggRow[] = useMemo(() => {
    if (allIssues.length === 0) return [];

    const runIndex = new Map<string, RunWithDomain>();
    allRuns.forEach((run) => runIndex.set(run.id, run));

    type Internal = {
      domainKind: DomainKind;
      scenarioId: string;
      occurrences: number;
      platformIds: Set<string>;
      firstStartedAt?: string;
      firstVersion?: string;
      latestStartedAt?: string;
      latestVersion?: string;
    };

    const map = new Map<string, Internal>();

    allIssues.forEach(({ issue, domainKind }) => {
      const run = runIndex.get(issue.runId);
      if (!run) return;

      const key = `${domainKind}|${issue.scenarioId}`;
      const existing = map.get(key);

      const startedAt = run.startedAt ?? '';
      const version = run.versionLabel ?? 'N/A';

      if (!existing) {
        const platformIds = new Set<string>([run.platformId]);
        map.set(key, {
          domainKind,
          scenarioId: issue.scenarioId,
          occurrences: 1,
          platformIds,
          firstStartedAt: startedAt || undefined,
          firstVersion: version,
          latestStartedAt: startedAt || undefined,
          latestVersion: version,
        });
      } else {
        existing.occurrences += 1;
        existing.platformIds.add(run.platformId);

        if (
          startedAt &&
          (!existing.firstStartedAt || startedAt < existing.firstStartedAt)
        ) {
          existing.firstStartedAt = startedAt;
          existing.firstVersion = version;
        }
        if (
          startedAt &&
          (!existing.latestStartedAt || startedAt > existing.latestStartedAt)
        ) {
          existing.latestStartedAt = startedAt;
          existing.latestVersion = version;
        }
      }
    });

    const rows: ScenarioAggRow[] = Array.from(map.values())
      .map((entry) => ({
        domainKind: entry.domainKind,
        scenarioId: entry.scenarioId,
        occurrences: entry.occurrences,
        affectedPlatforms: entry.platformIds.size,
        firstVersion: entry.firstVersion,
        latestVersion: entry.latestVersion,
      }))
      .sort((a, b) => b.occurrences - a.occurrences)
      .slice(0, 10);

    return rows;
  }, [allIssues, allRuns]);

  const latestRunsForTable = useMemo(
    () => allRuns.slice(0, 10),
    [allRuns],
  );

  // Heatmap FW + APP
  const fwHeatmapRows = useMemo(
    () => buildHeatmapRows(fwData, QUICKSET_SCENARIOS, getFwIssuesForRun),
    [fwData],
  );

  const appHeatmapRows = useMemo(
    () => buildHeatmapRows(appData, APP_SCENARIOS, getAppIssuesForRun),
    [appData],
  );

  return (
    <section>
      <h2 className="page-title">QA Reports · Global View</h2>
      <p className="page-subtitle">
        Cross-platform QA overview for firmware and Partner TV app – runs, pass
        rate, regressions and top failing scenarios in one place.
      </p>
      {isLoading && <p className="hint">Loading aggregated data...</p>}
      {loadError && (
        <p className="hint" style={{ color: '#e67e22' }}>
          {loadError}
        </p>
      )}

      {/* Global KPIs */}
      <div className="card">
        <h3>Global QA overview</h3>
        <p className="hint">
          High-level status of FW + App testing across all platforms and runs.
        </p>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
            gap: 16,
            marginTop: 8,
          }}
        >
          <div>
            <div className="filters-label">Total runs (FW + App)</div>
            <div style={{ fontSize: 22, fontWeight: 600 }}>{totalRuns}</div>
          </div>
          <div>
            <div className="filters-label">FW runs</div>
            <div style={{ fontSize: 22, fontWeight: 600 }}>{totalFwRuns}</div>
          </div>
          <div>
            <div className="filters-label">App runs</div>
            <div style={{ fontSize: 22, fontWeight: 600 }}>{totalAppRuns}</div>
          </div>
          <div>
            <div className="filters-label">Distinct platforms</div>
            <div style={{ fontSize: 22, fontWeight: 600 }}>{totalPlatforms}</div>
          </div>
          <div>
            <div className="filters-label">Scenarios executed</div>
            <div style={{ fontSize: 22, fontWeight: 600 }}>
              {totalScenarios}
            </div>
          </div>
          <div>
            <div className="filters-label">Global pass rate</div>
            <div style={{ fontSize: 22, fontWeight: 600 }}>
              {globalPassRate != null
                ? `${globalPassRate.toFixed(1)}%`
                : '–'}
            </div>
          </div>
          <div>
            <div className="filters-label">Issues logged</div>
            <div style={{ fontSize: 22, fontWeight: 600 }}>
              {allIssues.length}
            </div>
          </div>
        </div>
      </div>

      {/* Latest runs timeline */}
      <div className="card">
        <h3>Latest runs (FW + App)</h3>
        <p className="hint">
          Most recent QA sessions across firmware and app, sorted by start time.
        </p>
        <table className="table">
          <thead>
            <tr>
              <th>Domain</th>
              <th>Session ID</th>
              <th>Platform</th>
              <th>Version</th>
              <th>Started at</th>
              <th>Status</th>
              <th>Pass rate</th>
              <th>Scenarios (Passed/Total)</th>
            </tr>
          </thead>
          <tbody>
            {latestRunsForTable.length === 0 ? (
              <tr>
                <td
                  colSpan={8}
                  style={{ textAlign: 'center', padding: '16px 0' }}
                >
                  No runs available yet.
                </td>
              </tr>
            ) : (
              latestRunsForTable.map((run) => (
                <tr key={run.id}>
                  <td>{run.domainKind}</td>
                  <td>{run.sessionId}</td>
                  <td>{run.platformLabel}</td>
                  <td>{run.versionLabel}</td>
                  <td>{run.startedAt ?? '–'}</td>
                  <td>{run.status}</td>
                  <td>
                    {run.passRate != null ? `${run.passRate}%` : '–'}
                  </td>
                  <td>
                    {run.passedScenarios ?? 0}/{run.totalScenarios ?? 0}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Regression heatmap */}
      <div className="card">
        <h3>Regression heatmap</h3>
        <p className="hint">
          Scenario × platform matrix that shows where things are stable, where
          regressions exist now, and where they were fixed.
        </p>

        <h4>Firmware scenarios</h4>
        <table className="table heatmap-table">
          <thead>
            <tr>
              <th>Platform \\ Scenario</th>
              {QUICKSET_SCENARIOS.map((scenario) => (
                <th key={scenario.id}>{scenario.name ?? scenario.id}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {fwHeatmapRows.length === 0 ? (
              <tr>
                <td
                  colSpan={1 + QUICKSET_SCENARIOS.length}
                  style={{ textAlign: 'center', padding: '16px 0' }}
                >
                  No firmware runs available yet.
                </td>
              </tr>
            ) : (
              fwHeatmapRows.map((row) => (
                <tr key={row.platformId}>
                  <td>{row.platformLabel}</td>
                  {row.cells.map((cell) => (
                    <td key={cell.scenarioId}>
                      <span
                        className={[
                          'heatmap-cell',
                          statusToClass[cell.status],
                        ].join(' ')}
                      >
                        {statusToLabel[cell.status]}
                      </span>
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>

        <h4>App scenarios</h4>
        <table className="table heatmap-table">
          <thead>
            <tr>
              <th>Platform \\ Scenario</th>
              {APP_SCENARIOS.map((scenario) => (
                <th key={scenario.id}>{scenario.name ?? scenario.id}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {appHeatmapRows.length === 0 ? (
              <tr>
                <td
                  colSpan={1 + APP_SCENARIOS.length}
                  style={{ textAlign: 'center', padding: '16px 0' }}
                >
                  No app runs available yet.
                </td>
              </tr>
            ) : (
              appHeatmapRows.map((row) => (
                <tr key={row.platformId}>
                  <td>{row.platformLabel}</td>
                  {row.cells.map((cell) => (
                    <td key={cell.scenarioId}>
                      <span
                        className={[
                          'heatmap-cell',
                          statusToClass[cell.status],
                        ].join(' ')}
                      >
                        {statusToLabel[cell.status]}
                      </span>
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Top failing scenarios (regression candidates) */}
      <div className="card">
        <h3>Top failing scenarios (regression candidates)</h3>
        <p className="hint">
          Scenarios that appear most often in issues, grouped by domain. Helps
          you see where regressions or chronic problems sit.
        </p>
        <table className="table">
          <thead>
            <tr>
              <th>Domain</th>
              <th>Scenario ID</th>
              <th>Occurrences</th>
              <th>Affected platforms</th>
              <th>First version with issue</th>
              <th>Latest version with issue</th>
            </tr>
          </thead>
          <tbody>
            {topScenarioAgg.length === 0 ? (
              <tr>
                <td
                  colSpan={6}
                  style={{ textAlign: 'center', padding: '16px 0' }}
                >
                  No issues recorded yet, nothing to aggregate.
                </td>
              </tr>
            ) : (
              topScenarioAgg.map((row) => (
                <tr key={`${row.domainKind}-${row.scenarioId}`}>
                  <td>{row.domainKind}</td>
                  <td>{row.scenarioId}</td>
                  <td>{row.occurrences}</td>
                  <td>{row.affectedPlatforms}</td>
                  <td>{row.firstVersion ?? '–'}</td>
                  <td>{row.latestVersion ?? '–'}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
        <p className="hint">
          Use this table when you need to explain to dev / הנהלה איפה באמת
          כואב – איזה תסריטים שוברים גרסאות ומה המועמדים החזקים לג׳ירה.
        </p>
      </div>
    </section>
  );
};

export default Reports;
