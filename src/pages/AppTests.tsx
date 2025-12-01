// src/pages/AppTests.tsx
import React, { useEffect, useMemo, useState } from 'react';
import {
  APP_PLATFORMS,
  APP_SCENARIOS,
  APP_TEST_RUNS,
  loadAppVersions,
  saveAppVersions,
  getLatestAppRunForPlatform,
  getAppIssuesForRun,
  loadAppDashboardData,
  type Platform,
  type VersionUnderTest,
  type TestRunSummary,
  type TestStepIssue,
  type TestScenario,
} from '../services/appService';
import type { PlatformId } from '../types/domain';
import Modal from '../components/Modal';

type AppRow = {
  platformId: PlatformId;
  platformLabel: string;
  family?: string;
  vendor?: string;
  model?: string;
  activeVersionLabel?: string;
  channel?: string;
  latestRun?: TestRunSummary;
  highestPriorityScenario?: number;
};

type ScenarioHistoryRow = {
  run: TestRunSummary;
  versionLabel: string;
  platformLabel: string;
  hasIssueForScenario: boolean;
};

const safeLower = (value: unknown): string =>
  (value ?? '').toString().toLowerCase();

const AppTests: React.FC = () => {
  const [platforms, setPlatforms] = useState<Platform[]>(APP_PLATFORMS);
  const [versions, setVersions] = useState<VersionUnderTest[]>(() =>
    loadAppVersions(),
  );
  const [runs, setRuns] = useState<TestRunSummary[]>(APP_TEST_RUNS);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [selectedPlatformId, setSelectedPlatformId] =
    useState<PlatformId | 'ALL'>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  // History selectors (like FW Tests)
  const [historyPlatformId, setHistoryPlatformId] = useState<string>(
    APP_PLATFORMS[0]?.id ?? 'ANDROID_TV_VSTB',
  );
  const [historyScenarioId, setHistoryScenarioId] = useState<string>(
    APP_SCENARIOS[0]?.id ?? 'APP_LAUNCH_LIVE',
  );

  useEffect(() => {
    let isCancelled = false;

    const syncFromBackend = async () => {
      try {
        setIsLoading(true);
        setLoadError(null);
        const data = await loadAppDashboardData();
        if (isCancelled) return;

        setPlatforms(data.platforms.length ? data.platforms : APP_PLATFORMS);
        setVersions((prev) => {
          if (data.versions.length > 0) {
            saveAppVersions(data.versions);
            return data.versions;
          }
          return prev;
        });
        setRuns(data.runs.length ? data.runs : APP_TEST_RUNS);
      } catch (error) {
        console.error('[AppTests] Failed to load app data from backend', error);
        if (!isCancelled) {
          setLoadError(
            'Failed to sync app data from backend. Showing local data.',
          );
          setPlatforms(APP_PLATFORMS);
          setVersions(loadAppVersions());
          setRuns(APP_TEST_RUNS);
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    };

    void syncFromBackend();

    return () => {
      isCancelled = true;
    };
  }, []);

  const rows: AppRow[] = useMemo(() => {
    return platforms.map((platform) => {
      const platformVersions = versions.filter(
        (v) => v.platformId === platform.id && v.domain === 'APP',
      );
      const activeVersion =
        platformVersions.find((v) => v.isActive) ?? platformVersions[0];

      const latestRun =
        runs.find((run) => run.platformId === platform.id) ??
        getLatestAppRunForPlatform(platform.id, runs);

      const highestPriorityScenario = APP_SCENARIOS.reduce<
        number | undefined
      >((acc, scenario) => {
        if (scenario.priority == null) {
          return acc;
        }
        if (acc == null) {
          return scenario.priority;
        }
        return scenario.priority < acc ? scenario.priority : acc;
      }, undefined);

      return {
        platformId: platform.id,
        platformLabel: platform.label,
        family: platform.family,
        vendor: platform.vendor,
        model: platform.model,
        activeVersionLabel: activeVersion?.versionLabel,
        channel: activeVersion?.releaseChannel,
        latestRun,
        highestPriorityScenario,
      };
    });
  }, [platforms, versions, runs]);

  const filteredByPlatform = useMemo(() => {
    if (selectedPlatformId === 'ALL') {
      return rows;
    }
    return rows.filter((row) => row.platformId === selectedPlatformId);
  }, [rows, selectedPlatformId]);

  const filteredRows = useMemo(() => {
    const term = searchQuery.trim();
    if (!term) return filteredByPlatform;

    const tokens = term
      .split(/\s+/)
      .map((token) => token.trim())
      .filter(Boolean);

    if (tokens.length === 0) {
      return filteredByPlatform;
    }

    return filteredByPlatform.filter((row) => {
      const haystack: Array<string | undefined | null> = [
        row.platformLabel,
        row.activeVersionLabel,
        row.channel,
        row.family,
        row.vendor,
        row.model,
        row.latestRun?.status,
        row.latestRun?.testerId,
        row.latestRun?.sessionId,
      ];

      return tokens.some((token) => {
        const lowered = safeLower(token);
        return haystack.some((field) => safeLower(field).includes(lowered));
      });
    });
  }, [filteredByPlatform, searchQuery]);

  const selectedRun = useMemo(
    () => runs.find((run) => run.id === selectedRunId),
    [runs, selectedRunId],
  );

  const selectedRunPlatform = useMemo(
    () =>
      selectedRun
        ? platforms.find((p) => p.id === selectedRun.platformId)
        : undefined,
    [selectedRun, platforms],
  );

  const selectedRunVersion = useMemo(
    () =>
      selectedRun
        ? versions.find((v) => v.id === selectedRun.versionId)
        : undefined,
    [selectedRun, versions],
  );

  const selectedRunIssues: TestStepIssue[] = useMemo(() => {
    if (!selectedRunId) {
      return [];
    }
    return getAppIssuesForRun(selectedRunId);
  }, [selectedRunId]);

  // History data (per platform, like FW Tests)
  const historyRunsForPlatform: TestRunSummary[] = useMemo(
    () =>
      runs
        .filter((r) => r.platformId === historyPlatformId)
        .sort((a, b) => (a.startedAt || '').localeCompare(b.startedAt || '')),
    [historyPlatformId, runs],
  );

  // Scenario history across app versions – "מאיזה גרסה נדפק"
  const scenarioHistoryRows: ScenarioHistoryRow[] = useMemo(() => {
    return runs
      .map((run) => {
        const issues = getAppIssuesForRun(run.id);
        const hasIssueForScenario = issues.some(
          (i) => i.scenarioId === historyScenarioId,
        );
        const version = versions.find((v) => v.id === run.versionId);
        const platform = platforms.find((p) => p.id === run.platformId);

        return {
          run,
          versionLabel: version?.versionLabel ?? '–',
          platformLabel: platform?.label ?? run.platformId,
          hasIssueForScenario,
        };
      })
      .sort((a, b) =>
        (a.run.startedAt || '').localeCompare(b.run.startedAt || ''),
      );
  }, [historyScenarioId, runs, versions, platforms]);

  return (
    <section>
      <h2 className="page-title">Partner TV · App Tests</h2>
      <p className="page-subtitle">
        Test coverage for Partner TV application across STB Sys App, Android TV
        vSTB, Android Mobile, Smart TV (LG/Samsung), Apple TV and iOS – with
        version history, scenario regression view, priority filtering and quick
        search.
      </p>
      {isLoading && <p className="hint">Syncing app data from backend...</p>}
      {loadError && (
        <p className="hint" style={{ color: '#e67e22' }}>
          {loadError}
        </p>
      )}

      {/* Filters row */}
      <div className="card">
        <h3>Device / Platform & quick search</h3>
        <p className="hint">
          Filter by specific device/platform or search across tester, status, or
          session id.
        </p>
        <div className="filters-row">
          <div className="filters-item">
            <label className="filters-label" htmlFor="app-platform-filter">
              Device / Platform
            </label>
            <select
              id="app-platform-filter"
              className="top-bar-select"
              value={selectedPlatformId}
              onChange={(event) =>
                setSelectedPlatformId(event.target.value as PlatformId | 'ALL')
              }
            >
              <option value="ALL">All platforms</option>
              {platforms.map((platform) => (
                <option key={platform.id} value={platform.id}>
                  {platform.label}
                </option>
              ))}
            </select>
          </div>

          <div className="filters-item filters-item-grow">
            <label className="filters-label" htmlFor="app-quick-search">
              Quick search
            </label>
            <input
              id="app-quick-search"
              type="text"
              className="input-text"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Search by platform, version, tester, or status"
            />
          </div>
        </div>
      </div>

      {/* App scenarios (priority aware) */}
      <div className="card">
        <h3>App test scenarios (priority-aware)</h3>
        <p className="hint">
          Key Partner TV scenarios with their business priority to drive
          regression focus.
        </p>
        <table className="table">
          <thead>
            <tr>
              <th>Scenario ID</th>
              <th>Name</th>
              <th>Priority</th>
              <th>Description</th>
              <th>Tags</th>
            </tr>
          </thead>
          <tbody>
            {APP_SCENARIOS.map((scenario: TestScenario) => (
              <tr key={scenario.id}>
                <td>{scenario.id}</td>
                <td>{scenario.name}</td>
                <td>{scenario.priority ?? '–'}</td>
                <td>{scenario.description}</td>
                <td>{scenario.tags?.join(', ')}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="hint">
          Use priority to focus on the most critical user journeys first when
          time is limited.
        </p>
      </div>

      {/* Version history per platform (App) */}
      <div className="card">
        <h3>Version history · per platform (App)</h3>
        <p className="hint">
          Choose a device/platform to see how Partner TV app versions behaved
          over time (sessions, pass rate and failures).
        </p>
        <div className="filters-row">
          <div className="filters-item">
            <label className="filters-label" htmlFor="app-history-platform">
              Platform
            </label>
            <select
              id="app-history-platform"
              className="top-bar-select"
              value={historyPlatformId}
              onChange={(e) => setHistoryPlatformId(e.target.value)}
            >
              {platforms.map((platform) => (
                <option key={platform.id} value={platform.id}>
                  {platform.label}
                </option>
              ))}
            </select>
          </div>
        </div>
        <table className="table">
          <thead>
            <tr>
              <th>Session ID</th>
              <th>App version</th>
              <th>Started at</th>
              <th>Status</th>
              <th>Pass rate</th>
              <th>Scenarios (Passed/Failed)</th>
            </tr>
          </thead>
          <tbody>
            {historyRunsForPlatform.length === 0 ? (
              <tr>
                <td
                  colSpan={6}
                  style={{ textAlign: 'center', padding: '16px 0' }}
                >
                  No runs recorded yet for this platform.
                </td>
              </tr>
            ) : (
              historyRunsForPlatform.map((run) => {
                const version = versions.find((v) => v.id === run.versionId);
                return (
                  <tr key={run.id}>
                    <td>{run.sessionId}</td>
                    <td>{version?.versionLabel ?? '–'}</td>
                    <td>{run.startedAt}</td>
                    <td>{run.status}</td>
                    <td>{`${run.passRate}%`}</td>
                    <td>
                      {run.passedScenarios}/{run.totalScenarios} passed ·{' '}
                      {run.failedScenarios} failed
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Scenario history across app versions – "מאיזה גרסה נדפק" */}
      <div className="card">
        <h3>Scenario history · across app versions</h3>
        <p className="hint">
          Choose an app scenario to see how it behaved across platforms and app
          versions, and from which version a regression started.
        </p>
        <div className="filters-row">
          <div className="filters-item">
            <label className="filters-label" htmlFor="app-history-scenario">
              Scenario
            </label>
            <select
              id="app-history-scenario"
              className="top-bar-select"
              value={historyScenarioId}
              onChange={(e) => setHistoryScenarioId(e.target.value)}
            >
              {APP_SCENARIOS.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>
        </div>
        <table className="table">
          <thead>
            <tr>
              <th>Session ID</th>
              <th>Platform</th>
              <th>App version</th>
              <th>Status</th>
              <th>Has issue for scenario?</th>
            </tr>
          </thead>
          <tbody>
            {scenarioHistoryRows.length === 0 ? (
              <tr>
                <td
                  colSpan={5}
                  style={{ textAlign: 'center', padding: '16px 0' }}
                >
                  No runs recorded yet for this scenario.
                </td>
              </tr>
            ) : (
              scenarioHistoryRows.map((row) => (
                <tr key={row.run.id}>
                  <td>{row.run.sessionId}</td>
                  <td>{row.platformLabel}</td>
                  <td>{row.versionLabel}</td>
                  <td>{row.run.status}</td>
                  <td>
                    {row.hasIssueForScenario
                      ? 'Yes (regression / open)'
                      : 'No'}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Application status by platform */}
      <div className="card">
        <h3>Application test status by platform</h3>
        <p className="hint">
          Latest execution status, active version, channel and tester context
          for each supported platform.
        </p>
        <table className="table">
          <thead>
            <tr>
              <th>Platform</th>
              <th>Family</th>
              <th>Vendor / Model</th>
              <th>Active version</th>
              <th>Channel</th>
              <th>Highest priority</th>
              <th>Latest status</th>
              <th>Pass rate</th>
              <th>Tester / Session</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {filteredRows.length === 0 ? (
              <tr>
                <td
                  colSpan={10}
                  style={{ textAlign: 'center', padding: '16px 0' }}
                >
                  No platforms match the current filters.
                </td>
              </tr>
            ) : (
              filteredRows.map((row) => {
                const latest = row.latestRun;
                return (
                  <tr key={row.platformId}>
                    <td>{row.platformLabel}</td>
                    <td>{row.family ?? '–'}</td>
                    <td>
                      {row.vendor ?? '–'}
                      {row.model ? ` / ${row.model}` : ''}
                    </td>
                    <td>{row.activeVersionLabel ?? '–'}</td>
                    <td>{row.channel ?? '–'}</td>
                    <td>
                      {row.highestPriorityScenario != null
                        ? `P${row.highestPriorityScenario}`
                        : '–'}
                    </td>
                    <td>{latest?.status ?? 'NOT_STARTED'}</td>
                    <td>{latest ? `${latest.passRate}%` : '–'}</td>
                    <td>
                      {latest?.testerId ?? '–'}
                      {latest?.sessionId ? ` / ${latest.sessionId}` : ''}
                    </td>
                    <td>
                      {latest && (
                        <button
                          type="button"
                          className="btn-pill"
                          onClick={() => setSelectedRunId(latest.id)}
                        >
                          View
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Details modal */}
      <Modal
        open={!!selectedRun}
        title={selectedRun ? `Session Details · ${selectedRun.sessionId}` : ''}
        onClose={() => setSelectedRunId(null)}
      >
        {selectedRun && (
          <>
            <p className="page-subtitle">
              Platform:{' '}
              <strong>
                {selectedRunPlatform?.label ?? selectedRun.platformId}
              </strong>{' '}
              · App Version:{' '}
              <strong>{selectedRunVersion?.versionLabel ?? 'N/A'}</strong> ·
              Channel:{' '}
              <strong>{selectedRunVersion?.releaseChannel ?? 'N/A'}</strong> ·
              Status: <strong>{selectedRun.status}</strong> · Pass Rate:{' '}
              <strong>{selectedRun.passRate}%</strong>
            </p>

            <h4>Issues in this run</h4>
            {selectedRunIssues.length === 0 ? (
              <p>
                No issues recorded for this run (all scenarios passed or no
                issues logged).
              </p>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>Scenario</th>
                    <th>Step</th>
                    <th>Title</th>
                    <th>Description</th>
                    <th>Suspected Root Cause</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedRunIssues.map((issue) => {
                    const scenario = APP_SCENARIOS.find(
                      (s) => s.id === issue.scenarioId,
                    );
                    return (
                      <tr key={issue.id}>
                        <td>{scenario?.name ?? issue.scenarioId}</td>
                        <td>{issue.stepIndex}</td>
                        <td>{issue.title}</td>
                        <td>{issue.description}</td>
                        <td>{issue.suspectedRootCause ?? '–'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}

            <h4>Jira-ready text (example)</h4>
            <p className="hint">
              Copy the text below directly into Jira (Summary + Description).
              Same pattern as FW, so QA does not need to learn two different
              flows.
            </p>

            {selectedRunIssues.length === 0 ? (
              <p>No Jira issues suggested for this run.</p>
            ) : (
              selectedRunIssues.map((issue) => (
                <div key={issue.id} style={{ marginBottom: 16 }}>
                  <div>
                    <strong>Summary:</strong>
                  </div>
                  <pre style={{ whiteSpace: 'pre-wrap' }}>
                    {issue.jiraSummarySuggestion ??
                      `[${selectedRunPlatform?.label ?? selectedRun.platformId}][APP][${
                        issue.scenarioId
                      }] ${issue.title}`}
                  </pre>
                  <div>
                    <strong>Description:</strong>
                  </div>
                  <pre style={{ whiteSpace: 'pre-wrap' }}>
                    {issue.jiraDescriptionSuggestion ??
                      `Environment:
- Platform: ${selectedRunPlatform?.label ?? selectedRun.platformId}
- App: ${selectedRunVersion?.versionLabel ?? 'N/A'}
- Scenario: ${issue.scenarioId}

Issue:
${issue.description}

Suspected root cause:
${issue.suspectedRootCause ?? 'N/A'}`}
                  </pre>
                </div>
              ))
            )}
          </>
        )}
      </Modal>
    </section>
  );
};

export default AppTests;
