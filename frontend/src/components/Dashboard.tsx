import type { DashboardSummary } from '../types';
import { formatRelative } from '../utils/format';
import { Card, ErrorBanner, LoadingBlock, SectionTitle, StatusBadge } from './ui';

interface DashboardProps {
  summary: DashboardSummary | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  onSelectProject: (projectId: number) => void;
}

function Stat({ label, value, tone = 'default' }: { label: string; value: number; tone?: 'default' | 'bad' }) {
  return (
    <Card className="p-5">
      <p className="text-sm text-slate-500 dark:text-slate-400">{label}</p>
      <p
        className={`mt-1 text-3xl font-semibold tabular-nums ${
          tone === 'bad' && value > 0 ? 'text-red-600 dark:text-red-400' : 'text-slate-900 dark:text-white'
        }`}
      >
        {value}
      </p>
    </Card>
  );
}

export function Dashboard({ summary, loading, error, onRetry, onSelectProject }: DashboardProps) {
  if (error) return <ErrorBanner message={error} onRetry={onRetry} />;
  if (!summary) return loading ? <LoadingBlock label="Loading dashboard…" /> : null;

  const checked = summary.latest_checks.filter((p) => p.check);
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Projects" value={summary.project_count} />
        <Stat label="Checks run" value={summary.check_count} />
        <Stat label="Failed checks (all time)" value={summary.failed_check_count} tone="bad" />
        <Stat label="Projects currently failing" value={summary.failing_project_count} tone="bad" />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <section>
          <SectionTitle>Latest result per project</SectionTitle>
          <Card>
            {checked.length === 0 ? (
              <p className="p-6 text-sm text-slate-500 dark:text-slate-400">No health checks have been run yet.</p>
            ) : (
              <ul className="divide-y divide-slate-100 dark:divide-slate-800">
                {checked.map(({ project_id, project_name, check }) => (
                  <li key={project_id}>
                    <button
                      onClick={() => onSelectProject(project_id)}
                      className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-slate-50 dark:hover:bg-slate-800/50"
                    >
                      <span className="truncate font-medium">{project_name}</span>
                      <span className="flex shrink-0 items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
                        {check && formatRelative(check.timestamp)}
                        <StatusBadge status={check?.status} />
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </section>

        <section>
          <SectionTitle>Recent failures</SectionTitle>
          <Card>
            {summary.recent_failures.length === 0 ? (
              <p className="p-6 text-sm text-slate-500 dark:text-slate-400">No failed checks recorded.</p>
            ) : (
              <ul className="divide-y divide-slate-100 dark:divide-slate-800">
                {summary.recent_failures.map(({ project_id, project_name, check }) =>
                  check ? (
                    <li key={check.id}>
                      <button
                        onClick={() => onSelectProject(project_id)}
                        className="w-full px-4 py-3 text-left hover:bg-slate-50 dark:hover:bg-slate-800/50"
                      >
                        <div className="flex items-center justify-between gap-3">
                          <span className="truncate font-medium">{project_name}</span>
                          <span className="flex shrink-0 items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
                            {formatRelative(check.timestamp)}
                            <StatusBadge status={check.status} />
                          </span>
                        </div>
                        {check.error && (
                          <p className="mt-1 truncate font-mono text-xs text-red-700 dark:text-red-300">{check.error}</p>
                        )}
                      </button>
                    </li>
                  ) : null,
                )}
              </ul>
            )}
          </Card>
        </section>
      </div>
    </div>
  );
}
