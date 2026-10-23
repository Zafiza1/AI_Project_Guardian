import type { CheckCommand, HealthCheck, Project } from '../types';
import { formatTimestamp } from '../utils/format';
import { HealthCheckResults } from './HealthCheckResults';
import { Button, Card, SectionTitle, StatusBadge } from './ui';

interface ProjectDetailProps {
  project: Project;
  checkCommands: CheckCommand[];
  history: HealthCheck[];
  historyLoading: boolean;
  historyError: string | null;
  running: boolean;
  onRetryHistory: () => void;
  onRunCheck: () => void;
  onRemove: () => void;
  onClose: () => void;
}

export function ProjectDetail({
  project,
  checkCommands,
  history,
  historyLoading,
  historyError,
  running,
  onRetryHistory,
  onRunCheck,
  onRemove,
  onClose,
}: ProjectDetailProps) {
  const command = checkCommands.find((c) => c.id === project.check_command);
  const latest = project.latest_check;
  // While a run is in progress, show branch/working-tree data from the most recent finished run.
  const lastFinished = latest?.status === 'running' ? (history.find((c) => c.status !== 'running') ?? null) : latest;

  return (
    <div className="space-y-4">
      <Card className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="truncate text-lg font-semibold">{project.display_name}</h2>
              <StatusBadge status={latest?.status} />
            </div>
            <p className="mt-1 break-all font-mono text-xs text-slate-500 dark:text-slate-400">{project.repository_path}</p>
          </div>
          <div className="flex gap-2">
            <Button loading={running} onClick={onRunCheck}>
              {running ? 'Running check…' : 'Run health check'}
            </Button>
            <Button variant="secondary" onClick={onClose} aria-label="Close details">
              ✕
            </Button>
          </div>
        </div>

        <dl className="mt-4 grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
          <div>
            <dt className="text-xs text-slate-500 dark:text-slate-400">Branch</dt>
            <dd className="font-mono">{lastFinished?.branch ?? '—'}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500 dark:text-slate-400">Working tree</dt>
            <dd>
              {lastFinished?.is_clean == null
                ? '—'
                : lastFinished.is_clean
                  ? 'Clean'
                  : `${lastFinished.changed_files} changed file(s)`}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500 dark:text-slate-400">Check command</dt>
            <dd className="font-mono">{command ? command.label : project.check_command ?? 'None (Git only)'}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500 dark:text-slate-400">Registered</dt>
            <dd>{formatTimestamp(project.created_at)}</dd>
          </div>
        </dl>
        {lastFinished && (
          <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">
            Branch and working-tree values come from the latest finished check ({formatTimestamp(lastFinished.timestamp)}).
          </p>
        )}
      </Card>

      <section>
        <SectionTitle
          action={
            <Button variant="danger" onClick={onRemove} className="py-1 text-xs">
              Remove from Guardian
            </Button>
          }
        >
          Run history &amp; logs
        </SectionTitle>
        <HealthCheckResults healthChecks={history} loading={historyLoading} error={historyError} onRetry={onRetryHistory} />
      </section>
    </div>
  );
}
