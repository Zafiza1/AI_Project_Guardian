import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from './api/client';
import { AddProjectForm } from './components/AddProjectForm';
import { Dashboard } from './components/Dashboard';
import { ProjectDetail } from './components/ProjectDetail';
import { ProjectList } from './components/ProjectList';
import { ErrorBanner, SectionTitle } from './components/ui';
import type { CheckCommand, DashboardSummary, GuardianSettings, HealthCheck, Project } from './types';

const errorMessage = (err: unknown) => (err instanceof Error ? err.message : String(err));

const POLL_INTERVAL_MS = 1500;

function useTheme() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains('dark'));
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark);
    try {
      localStorage.setItem('theme', dark ? 'dark' : 'light');
    } catch {
      // Storage may be unavailable (private mode); the theme still applies for this session.
    }
  }, [dark]);
  return [dark, () => setDark((d) => !d)] as const;
}

function App() {
  const [dark, toggleTheme] = useTheme();

  const [settings, setSettings] = useState<GuardianSettings | null>(null);
  const [checkCommands, setCheckCommands] = useState<CheckCommand[]>([]);
  const [metaError, setMetaError] = useState<string | null>(null);

  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  const [projects, setProjects] = useState<Project[]>([]);
  const [projectsLoading, setProjectsLoading] = useState(true);
  const [projectsError, setProjectsError] = useState<string | null>(null);

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const selectedIdRef = useRef<number | null>(null);
  useEffect(() => {
    selectedIdRef.current = selectedId;
  }, [selectedId]);
  const [history, setHistory] = useState<HealthCheck[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);

  // Projects whose "Run check" request is in flight (before the backend reports the run as 'running').
  const [startingIds, setStartingIds] = useState<Set<number>>(new Set());
  const [actionError, setActionError] = useState<string | null>(null);

  const loadMeta = useCallback(async () => {
    try {
      const [s, c] = await Promise.all([api.getSettings(), api.getCheckCommands()]);
      setSettings(s);
      setCheckCommands(c);
      setMetaError(null);
    } catch (err) {
      setMetaError(errorMessage(err));
    }
  }, []);

  const loadSummary = useCallback(async () => {
    try {
      setSummary(await api.getDashboard());
      setSummaryError(null);
    } catch (err) {
      setSummaryError(errorMessage(err));
    } finally {
      setSummaryLoading(false);
    }
  }, []);

  const loadProjects = useCallback(async () => {
    try {
      setProjects(await api.getProjects());
      setProjectsError(null);
    } catch (err) {
      setProjectsError(errorMessage(err));
    } finally {
      setProjectsLoading(false);
    }
  }, []);

  const loadHistory = useCallback(async (projectId: number) => {
    setHistoryLoading(true);
    try {
      setHistory(await api.getHealthChecks(projectId));
      setHistoryError(null);
    } catch (err) {
      setHistoryError(errorMessage(err));
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  const refreshAll = useCallback(() => {
    loadMeta();
    loadSummary();
    loadProjects();
  }, [loadMeta, loadSummary, loadProjects]);

  const selectProject = useCallback(
    (projectId: number | null) => {
      setSelectedId(projectId);
      setHistory([]);
      // Keep the selection in the URL (#project=3) so it survives reloads and can be bookmarked.
      window.history.replaceState(null, '', projectId === null ? window.location.pathname : `#project=${projectId}`);
      if (projectId !== null) loadHistory(projectId);
    },
    [loadHistory],
  );

  useEffect(() => {
    // Initial fetch from the backend (an external system); state is only set after the requests resolve.
    // oxlint-disable-next-line react/set-state-in-effect
    refreshAll();
    const match = /^#project=(\d+)$/.exec(window.location.hash);
    if (match) selectProject(Number(match[1]));
  }, [refreshAll, selectProject]);

  // Checks run in the background on the backend; poll while any project's latest run is still 'running'.
  // Deriving this from server data means polling also resumes after a page reload.
  const activeIds = new Set(projects.filter((p) => p.latest_check?.status === 'running').map((p) => p.id));
  const runningIds = new Set([...activeIds, ...startingIds]);
  const hasActiveChecks = activeIds.size > 0;

  useEffect(() => {
    if (!hasActiveChecks) return;
    const timer = window.setInterval(async () => {
      // Projects first, so the history fetched afterwards is at least as fresh.
      await loadProjects();
      const selected = selectedIdRef.current;
      await Promise.all([loadSummary(), selected !== null ? loadHistory(selected) : null]);
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [hasActiveChecks, loadProjects, loadSummary, loadHistory]);

  const runCheck = async (projectId: number) => {
    setStartingIds((s) => new Set(s).add(projectId));
    setActionError(null);
    try {
      await api.runHealthCheck(projectId);
    } catch (err) {
      setActionError(`Health check could not be started: ${errorMessage(err)}`);
    } finally {
      await Promise.all([
        loadProjects(),
        loadSummary(),
        selectedIdRef.current === projectId ? loadHistory(projectId) : null,
      ]);
      setStartingIds((s) => {
        const next = new Set(s);
        next.delete(projectId);
        return next;
      });
    }
  };

  const removeProject = async (project: Project) => {
    if (!confirm(`Remove "${project.display_name}" and its check history from Guardian?\n\nThe repository on disk is not touched.`)) return;
    setActionError(null);
    try {
      await api.deleteProject(project.id);
      selectProject(null);
      await Promise.all([loadProjects(), loadSummary()]);
    } catch (err) {
      setActionError(`Could not remove project: ${errorMessage(err)}`);
    }
  };

  const selected = projects.find((p) => p.id === selectedId) ?? null;

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/80 backdrop-blur dark:border-slate-800 dark:bg-slate-950/80">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-indigo-600 text-sm font-bold text-white">G</span>
            <div>
              <h1 className="text-base font-semibold leading-tight">AI Project Guardian</h1>
              <p className="text-xs text-slate-500 dark:text-slate-400">Local repository health checks</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {settings?.read_only && (
              <span
                title="Guardian never modifies, commits, pushes, merges, or deploys."
                className="rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-medium text-emerald-800 dark:bg-emerald-500/10 dark:text-emerald-300"
              >
                Read-only mode
              </span>
            )}
            <button
              onClick={toggleTheme}
              className="rounded-md p-2 text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
              aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
            >
              {dark ? '☀︎' : '☾'}
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-8 px-4 py-6 sm:px-6">
        {metaError && <ErrorBanner message={metaError} onRetry={refreshAll} />}
        {actionError && <ErrorBanner message={actionError} onDismiss={() => setActionError(null)} />}

        <Dashboard
          summary={summary}
          loading={summaryLoading}
          error={metaError ? null : summaryError}
          onRetry={loadSummary}
          onSelectProject={selectProject}
        />

        <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
          <div className="space-y-6">
            <section>
              <SectionTitle>Projects</SectionTitle>
              <ProjectList
                projects={projects}
                loading={projectsLoading}
                error={metaError ? null : projectsError}
                onRetry={loadProjects}
                selectedProjectId={selectedId}
                runningIds={runningIds}
                onSelect={selectProject}
                onRunCheck={runCheck}
              />
            </section>
            <AddProjectForm
              checkCommands={checkCommands}
              settings={settings}
              onProjectAdded={(p) => {
                loadProjects();
                loadSummary();
                selectProject(p.id);
              }}
            />
          </div>

          <div>
            {selected ? (
              <ProjectDetail
                project={selected}
                checkCommands={checkCommands}
                history={history}
                historyLoading={historyLoading}
                historyError={historyError}
                running={runningIds.has(selected.id)}
                onRetryHistory={() => loadHistory(selected.id)}
                onRunCheck={() => runCheck(selected.id)}
                onRemove={() => removeProject(selected)}
                onClose={() => selectProject(null)}
              />
            ) : (
              <div className="grid h-full min-h-48 place-items-center rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500 dark:border-slate-700 dark:text-slate-400">
                Select a project to see its details, run history, and logs.
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
