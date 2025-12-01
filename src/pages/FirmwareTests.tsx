// src/pages/FirmwareTests.tsx
import React, { useEffect, useMemo, useState } from 'react';
import {
  FW_PLATFORMS,
  QUICKSET_SCENARIOS,
  FW_TEST_RUNS,
  getLatestRunForPlatform,
  getIssuesForRun,
  loadFwVersions,
  saveFwVersions,
  loadFirmwareDashboardData,
  type Platform,
  type TestRunSummary,
  type TestStepIssue,
  type TestScenario,
  type VersionUnderTest
} from '../services/fwService';

import type { PlatformId } from '../types/domain';
import Modal from '../components/Modal';

type SearchSuggestion = {
  id: string;
  label: string;
  kind: 'session' | 'scenario' | 'version';
  platformId?: PlatformId;
};

const safeLower = (value: unknown): string => (value ?? '').toString().toLowerCase();

// Compare two version labels like "3.2.0" vs "3.10.1".
// Returns:
//  -1 if a < b
//   0 if a == b
//   1 if a > b
function compareVersionLabels(a: string, b: string): number {
  const parse = (label: string): number[] =>
    label
      .split(/[.\-_\s]+/)
      .map((part) => parseInt(part, 10))
      .filter((n) => !Number.isNaN(n));

  const va = parse(a);
  const vb = parse(b);

  if (va.length === 0 || vb.length === 0) {
    // לא הצלחנו לפרש כמספרים – לא חוסמים, מתייחסים כשווים
    return 0;
  }

  const maxLen = Math.max(va.length, vb.length);
  for (let i = 0; i < maxLen; i += 1) {
    const na = va[i] ?? 0;
    const nb = vb[i] ?? 0;
    if (na < nb) return -1;
    if (na > nb) return 1;
  }
  return 0;
}

// Highest existing version label for given (platformId, channel)
function getHighestVersionLabelForPlatformChannel(
  versions: VersionUnderTest[],
  platformId: PlatformId,
  channel: 'DEV' | 'QA' | 'STAGE' | 'PROD'
): string | null {
  const relevant = versions.filter(
    (v) => v.platformId === platformId && v.releaseChannel === channel && !!v.versionLabel
  );
  if (relevant.length === 0) return null;

  return relevant
    .map((v) => v.versionLabel)
    .reduce((acc, cur) => (compareVersionLabels(cur, acc) > 0 ? cur : acc));
}

const FirmwareTests: React.FC = () => {
  const [platforms, setPlatforms] = useState<Platform[]>(FW_PLATFORMS);
  const [versions, setVersions] = useState<VersionUnderTest[]>(() => loadFwVersions());
  const [runs, setRuns] = useState<TestRunSummary[]>(FW_TEST_RUNS);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // add-new-version form
  const [newFwPlatformId, setNewFwPlatformId] = useState<PlatformId>('SEI_X4_FW');
  const [newFwVersionLabel, setNewFwVersionLabel] = useState<string>('');
  const [newFwReleaseChannel, setNewFwReleaseChannel] = useState<'DEV' | 'QA' | 'STAGE' | 'PROD'>(
    'QA'
  );

  // search
  const [searchQuery, setSearchQuery] = useState<string>('');

  // modal + filters
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [priorityFilter, setPriorityFilter] = useState<number | 0>(0); // 0 = All
  const [historyPlatformId, setHistoryPlatformId] = useState<string>('SEI_X4_FW');
  const [historyScenarioId, setHistoryScenarioId] = useState<string>('TV_AUTO_SYNC');

  useEffect(() => {
    let isCancelled = false;

    const syncFromBackend = async () => {
      try {
        setIsLoading(true);
        setLoadError(null);
        const data = await loadFirmwareDashboardData();
        if (isCancelled) return;

        setPlatforms(data.platforms.length ? data.platforms : FW_PLATFORMS);
        setVersions((prev) => {
          if (data.versions.length > 0) {
            saveFwVersions(data.versions);
            return data.versions;
          }
          return prev;
        });
        setRuns(data.runs.length ? data.runs : FW_TEST_RUNS);
      } catch (error) {
        console.error('[FirmwareTests] Failed to load data from backend', error);
        if (!isCancelled) {
          setLoadError('Failed to sync data from backend. Showing local data.');
          setPlatforms(FW_PLATFORMS);
          setVersions(loadFwVersions());
          setRuns(FW_TEST_RUNS);
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

  const selectedRun: TestRunSummary | undefined = useMemo(
    () => runs.find((run) => run.id === selectedRunId),
    [runs, selectedRunId]
  );

  const selectedRunIssues: TestStepIssue[] = useMemo(
    () => (selectedRunId ? getIssuesForRun(selectedRunId) : []),
    [selectedRunId]
  );

  const selectedRunPlatform = useMemo(
    () => (selectedRun ? platforms.find((p) => p.id === selectedRun.platformId) : undefined),
    [selectedRun, platforms]
  );

  const selectedRunVersion = useMemo(
    () => (selectedRun ? versions.find((v) => v.id === selectedRun.versionId) : undefined),
    [selectedRun, versions]
  );

  const filteredQuicksetScenarios: TestScenario[] = useMemo(
    () =>
      QUICKSET_SCENARIOS.filter((s) =>
        priorityFilter === 0 ? true : s.priority === priorityFilter
      ),
    [priorityFilter]
  );

  const historyRunsForPlatform: TestRunSummary[] = useMemo(
    () =>
      runs
        .filter((r) => r.platformId === historyPlatformId)
        .sort((a, b) => (a.startedAt || '').localeCompare(b.startedAt || '')),
    [historyPlatformId, runs]
  );

  const scenarioHistoryRows = useMemo(() => {
    return runs.map((run) => {
      const issues = getIssuesForRun(run.id);
      const hasIssueForScenario = issues.some((i) => i.scenarioId === historyScenarioId);
      const version = versions.find((v) => v.id === run.versionId);
      const platform = platforms.find((p) => p.id === run.platformId);

      return {
        run,
        versionLabel: version?.versionLabel ?? '–',
        platformLabel: platform?.label ?? run.platformId,
        hasIssueForScenario
      };
    }).sort((a, b) => (a.run.startedAt || '').localeCompare(b.run.startedAt || ''));
  }, [historyScenarioId, runs, versions, platforms]);

  const searchSuggestions: SearchSuggestion[] = useMemo(() => {
    const query = searchQuery.trim();
    if (!query) return [];
    const queryLower = safeLower(query);

    const results: SearchSuggestion[] = [];

    // sessions
    runs.forEach((run) => {
      if (safeLower(run.sessionId).includes(queryLower)) {
        const platform = platforms.find((p) => p.id === run.platformId);
        const version = versions.find((v) => v.id === run.versionId);
        results.push({
          id: run.id,
          kind: 'session',
          platformId: run.platformId as PlatformId,
          label: `[Session] ${run.sessionId} · ${platform?.label ?? run.platformId} · FW ${
            version?.versionLabel ?? 'N/A'
          }`
        });
      }
    });

    // scenarios
    QUICKSET_SCENARIOS.forEach((s) => {
      const match =
        safeLower(s.id).includes(queryLower) ||
        safeLower(s.name).includes(queryLower) ||
        safeLower(s.description).includes(queryLower);
      if (match) {
        results.push({
          id: s.id,
          kind: 'scenario',
          label: `[Scenario] ${s.name} (P${s.priority ?? '-'}, ${s.id})`
        });
      }
    });

    // versions
    versions.forEach((v) => {
      const match =
        safeLower(v.versionLabel).includes(queryLower) ||
        safeLower(v.releaseChannel).includes(queryLower);
      if (match) {
        const platform = platforms.find((p) => p.id === v.platformId);
        results.push({
          id: v.id,
          kind: 'version',
          platformId: v.platformId as PlatformId,
          label: `[Version] FW ${v.versionLabel} · ${platform?.label ?? v.platformId} · ${
            v.releaseChannel ?? ''
          }`
        });
      }
    });

    return results.slice(0, 12);
  }, [searchQuery, runs, versions, platforms]);

  const handleSuggestionClick = (s: SearchSuggestion) => {
    if (s.kind === 'session') {
      setSelectedRunId(s.id);
    } else if (s.kind === 'scenario') {
      setHistoryScenarioId(s.id);
    } else if (s.kind === 'version' && s.platformId) {
      setHistoryPlatformId(s.platformId);
    }
    setSearchQuery('');
  };

  const handleAddFwVersion = (event: React.FormEvent) => {
    event.preventDefault();
    const label = newFwVersionLabel.trim();
    if (!label) return;

    const id = `FW_${label.replace(/\s+/g, '_')}_${newFwPlatformId}`;
    const exists = versions.some((v) => v.id === id);
    if (exists) {
      window.alert('This firmware version already exists for this platform.');
      setNewFwVersionLabel('');
      return;
    }

    // Highest existing version for this platform *and* this channel
    const highestLabel = getHighestVersionLabelForPlatformChannel(
      versions,
      newFwPlatformId,
      newFwReleaseChannel
    );

    if (highestLabel) {
      const cmp = compareVersionLabels(label, highestLabel);
      if (cmp < 0) {
        window.alert(
          `Cannot add FW version "${label}". It is LOWER than existing version "${highestLabel}" in channel "${newFwReleaseChannel}".`
        );
        return;
      }
    }

    const newVersion: VersionUnderTest = {
      id,
      domain: 'FIRMWARE',
      platformId: newFwPlatformId,
      versionLabel: label,
      releaseChannel: newFwReleaseChannel,
      isActive: true
    };

    setVersions((prev) => {
      // מורידים isActive מכל הגרסאות של אותה פלטפורמה (כל ה־channels)
      const cleared = prev.map((v) =>
        v.platformId === newFwPlatformId ? { ...v, isActive: false } : v
      );
      const updated = [...cleared, newVersion];
      saveFwVersions(updated);
      return updated;
    });
    setNewFwVersionLabel('');
  };

  return (
    <section>
      <h2 className="page-title">FW Tests · STB</h2>
      <p className="page-subtitle">
        Firmware validation for S70PCI, Jade and SEI X4 using QuickSet flows (TV_AUTO_SYNC, Remote
        Pair / Unpair, Battery Status). Includes version history per platform, scenario regression
        view, priority-based filtering and quick search.
      </p>
      {isLoading && <p className="hint">Syncing firmware data from backend...</p>}
      {loadError && (
        <p className="hint" style={{ color: '#e67e22' }}>
          {loadError}
        </p>
      )}

      {/* Quick search */}
      <div className="card">
        <h3>Quick Search</h3>
        <p className="hint">
          Search across sessions, scenarios and FW versions. Selecting a result יפתח מודל או יעדכן
          את ההיסטוריה הרלוונטית.
        </p>
        <div style={{ marginBottom: 8 }}>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by session ID, scenario name, FW version..."
            style={{
              width: '100%',
              padding: '6px 10px',
              borderRadius: 8,
              border: '1px solid rgba(255,255,255,0.18)',
              background: 'transparent',
              color: 'inherit',
              fontSize: 13
            }}
          />
        </div>
        {searchSuggestions.length > 0 && (
          <div
            style={{
              borderRadius: 8,
              border: '1px solid rgba(255,255,255,0.12)',
              padding: '6px 8px',
              maxHeight: 180,
              overflowY: 'auto',
              fontSize: 12
            }}
          >
            {searchSuggestions.map((s) => (
              <div
                key={`${s.kind}-${s.id}`}
                onClick={() => handleSuggestionClick(s)}
                style={{
                  padding: '4px 4px',
                  cursor: 'pointer',
                  borderRadius: 4
                }}
                onMouseEnter={(e) => {
                  (e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.04)');
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget.style.backgroundColor = 'transparent');
                }}
              >
                {s.label}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Summary table per STB model */}
      <div className="card">
        <h3>STB Models · Latest FW Status</h3>
        <table className="table">
          <thead>
            <tr>
              <th>Model</th>
              <th>Vendor</th>
              <th>Current FW</th>
              <th>Last Session</th>
              <th>Pass Rate</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {platforms.map((platform) => {
              const activeVersion = versions.find(
                (v) => v.platformId === platform.id && v.isActive
              );
              const latestRun = getLatestRunForPlatform(platform.id, runs);

              return (
                <tr key={platform.id}>
                  <td>{platform.model}</td>
                  <td>{platform.vendor}</td>
                  <td>{activeVersion?.versionLabel ?? '–'}</td>
                  <td>{latestRun?.sessionId ?? '–'}</td>
                  <td>{latestRun ? `${latestRun.passRate}%` : '–'}</td>
                  <td>{latestRun?.status ?? 'NOT_STARTED'}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Add new FW version */}
      <div className="card">
        <h3>Add New FW Version for Testing</h3>
        <p className="hint">
          Choose STB model and enter a FW version label to start tracking it in the UI. הגרסה
          שתוסיף תהפוך ל־Current FW עבור הפלטפורמה – בתנאי שהיא לא נמוכה יותר מהגרסה
          הגבוהה ביותר הקיימת באותו Channel.
        </p>
        <form
          onSubmit={handleAddFwVersion}
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: 8,
            alignItems: 'center'
          }}
        >
          <label>
            Platform:{' '}
            <select
              value={newFwPlatformId}
              onChange={(e) => setNewFwPlatformId(e.target.value as PlatformId)}
              className="top-bar-select"
            >
              {platforms.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            FW version:{' '}
            <input
              type="text"
              value={newFwVersionLabel}
              onChange={(e) => setNewFwVersionLabel(e.target.value)}
              placeholder="e.g. 3.2.0"
              style={{
                padding: '4px 8px',
                borderRadius: 8,
                border: '1px solid rgba(255,255,255,0.18)',
                background: 'transparent',
                color: 'inherit',
                fontSize: 13
              }}
            />
          </label>
          <label>
            Channel:{' '}
            <select
              value={newFwReleaseChannel}
              onChange={(e) =>
                setNewFwReleaseChannel(e.target.value as 'DEV' | 'QA' | 'STAGE' | 'PROD')
              }
              className="top-bar-select"
            >
              <option value="DEV">DEV</option>
              <option value="QA">QA</option>
              <option value="STAGE">STAGE</option>
              <option value="PROD">PROD</option>
            </select>
          </label>
          <button type="submit" className="sidebar-item">
            Add
          </button>
        </form>
      </div>

      {/* Version history per platform (dropdown) */}
      <div className="card">
        <h3>Version History · Per Platform</h3>
        <p className="hint">
          Choose a platform to see how FW versions behaved over time (sessions, pass rate and
          status). This answers: &quot;מה היה מצב הבדיקות בגרסה קודמת?&quot;
        </p>
        <div style={{ marginBottom: 12 }}>
          <label>
            Platform:{' '}
            <select
              value={historyPlatformId}
              onChange={(e) => setHistoryPlatformId(e.target.value)}
              className="top-bar-select"
            >
              {platforms.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <table className="table">
          <thead>
            <tr>
              <th>Session ID</th>
              <th>FW Version</th>
              <th>Started At</th>
              <th>Status</th>
              <th>Pass Rate</th>
              <th>Scenarios (Passed/Failed)</th>
            </tr>
          </thead>
          <tbody>
            {historyRunsForPlatform.map((run) => {
              const version = versions.find((v) => v.id === run.versionId);
              return (
                <tr key={run.id}>
                  <td>{run.sessionId}</td>
                  <td>{version?.versionLabel ?? '–'}</td>
                  <td>{run.startedAt}</td>
                  <td>{run.status}</td>
                  <td>{`${run.passRate}%`}</td>
                  <td>
                    {run.passedScenarios}/{run.totalScenarios} passed · {run.failedScenarios} failed
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* QuickSet scenarios with priority filter */}
      <div className="card">
        <h3>QuickSet Scenarios (Domain Model, Priority-aware)</h3>
        <div style={{ marginBottom: 12 }}>
          <label>
            Priority filter:{' '}
            <select
              value={priorityFilter}
              onChange={(e) => setPriorityFilter(Number(e.target.value))}
              className="top-bar-select"
            >
              <option value={0}>All</option>
              <option value={1}>1 – Critical</option>
              <option value={2}>2 – High</option>
              <option value={3}>3 – Medium</option>
              <option value={4}>4 – Low</option>
              <option value={5}>5 – Very Low</option>
            </select>
          </label>
        </div>
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
            {filteredQuicksetScenarios.map((scenario) => (
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
          Priority can be used to focus on critical flows (1–2) first. Filter above updates the
          table without changing the underlying domain model.
        </p>
      </div>

      {/* Scenario history across versions – "מאיזה גרסה נדפק" */}
      <div className="card">
        <h3>Scenario History · Across FW Versions</h3>
        <p className="hint">
          Choose a QuickSet scenario to see how it behaved across platforms and FW versions, and
          from which version a regression started.
        </p>
        <div style={{ marginBottom: 12, display: 'flex', gap: 16 }}>
          <label>
            Scenario:{' '}
            <select
              value={historyScenarioId}
              onChange={(e) => setHistoryScenarioId(e.target.value)}
              className="top-bar-select"
            >
              {QUICKSET_SCENARIOS.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <table className="table">
          <thead>
            <tr>
              <th>Session ID</th>
              <th>Platform</th>
              <th>FW Version</th>
              <th>Status</th>
              <th>Has Issue for Scenario?</th>
            </tr>
          </thead>
          <tbody>
            {scenarioHistoryRows.map((row) => (
              <tr key={row.run.id}>
                <td>{row.run.sessionId}</td>
                <td>{row.platformLabel}</td>
                <td>{row.versionLabel}</td>
                <td>{row.run.status}</td>
                <td>{row.hasIssueForScenario ? 'Yes (regression / open)' : 'No'}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="hint">
          A scenario is marked &quot;Yes&quot; when there is at least one TestStepIssue linked to
          that scenario in the session. The first FW version where &quot;Yes&quot; appears is your
          regression start point.
        </p>
      </div>

      {/* Recent QuickSet runs */}
      <div className="card">
        <h3>Recent QuickSet Sessions (Example Data)</h3>
        <table className="table">
          <thead>
            <tr>
              <th>Session ID</th>
              <th>Tester</th>
              <th>Platform</th>
              <th>FW</th>
              <th>Status</th>
              <th>Pass Rate</th>
              <th>Scenarios (Passed/Failed)</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => {
              const platform = platforms.find((p) => p.id === run.platformId);
              const version = versions.find((v) => v.id === run.versionId);
              return (
                <tr key={run.id}>
                  <td>{run.sessionId}</td>
                  <td>{run.testerId ?? '–'}</td>
                  <td>{platform?.label ?? run.platformId}</td>
                  <td>{version?.versionLabel ?? '–'}</td>
                  <td>{run.status}</td>
                  <td>{`${run.passRate}%`}</td>
                  <td>
                    {run.passedScenarios}/{run.totalScenarios} passed · {run.failedScenarios} failed
                  </td>
                  <td>
                    <button
                      type="button"
                      className="sidebar-item"
                      onClick={() => setSelectedRunId(run.id)}
                    >
                      View
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Modal details */}
      <Modal
        open={!!selectedRun}
        title={selectedRun ? `Session Details · ${selectedRun.sessionId}` : ''}
        onClose={() => setSelectedRunId(null)}
      >
        {selectedRun && (
          <>
            <p className="page-subtitle">
              Tester: <strong>{selectedRun.testerId ?? 'N/A'}</strong> · Platform:{' '}
              <strong>{selectedRunPlatform?.label ?? selectedRun.platformId}</strong> · FW:{' '}
              <strong>{selectedRunVersion?.versionLabel ?? 'N/A'}</strong> · Status:{' '}
              <strong>{selectedRun.status}</strong> · Pass Rate:{' '}
              <strong>{selectedRun.passRate}%</strong>
            </p>

            <h4>Issues in this run</h4>
            {selectedRunIssues.length === 0 ? (
              <p>No issues recorded for this run (all scenarios passed or no issues logged).</p>
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
                    const scenario = QUICKSET_SCENARIOS.find((s) => s.id === issue.scenarioId);
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
              Copy the text below directly into Jira (Summary + Description). In a real integration,
              these strings will be auto-generated from the session log.
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
`[${selectedRunPlatform?.model ?? selectedRun.platformId}][QuickSet][${issue.scenarioId}] ${issue.title}`}
                  </pre>
                  <div>
                    <strong>Description:</strong>
                  </div>
                  <pre style={{ whiteSpace: 'pre-wrap' }}>
{issue.jiraDescriptionSuggestion ??
`Environment:
- Platform: ${selectedRunPlatform?.label ?? selectedRun.platformId}
- FW: ${selectedRunVersion?.versionLabel ?? 'N/A'}
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

export default FirmwareTests;
