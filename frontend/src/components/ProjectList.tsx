import type { Project } from '../types';
import { formatRelative } from '../utils/format';
import { BranchIcon, Button, Card, EmptyState, ErrorBanner, LoadingBlock, StatusBadge } from './ui';

interface ProjectListProps {
  projects: Project[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  selectedProjectId: number | null;
  runningIds: Set<number>;
  onSelect: (projectId: number) => void;
  onRunCheck: (projectId: number) => void;
}

export function ProjectList({
  projects,
  loading,
  error,
  onRetry,
  selectedProjectId,
  runningIds,
  onSelect,
  onRunCheck,
}: ProjectListProps) {
  if (error) return <ErrorBanner message={error} onRetry={onRetry} />;

  return (
    <Card>
      {loading && projects.length === 0 ? (
        <LoadingBlock label="Loading projects…" />
      ) : projects.length === 0 ? (
        <EmptyState title="No projects registered yet" hint="Register a local Git repository to start monitoring it." />
      ) : (
        <ul className="divide-y divide-slate-100 dark:divide-slate-800">
          {projects.map((project) => {
            const selected = project.id === selectedProjectId;
            const running = runningIds.has(project.id);
            return (
              <li
                key={project.id}
                className={`flex items-center gap-3 px-4 py-3 ${selected ? 'bg-indigo-50 dark:bg-indigo-500/10' : ''}`}
              >
                <button onClick={() => onSelect(project.id)} className="min-w-0 flex-1 text-left">
                  <div className="flex items-center gap-2">
                    <span className="truncate font-medium">{project.display_name}</span>
                    <StatusBadge status={project.latest_check?.status} />
                  </div>
                  <p className="mt-0.5 truncate font-mono text-xs text-slate-500 dark:text-slate-400">
                    {project.repository_path}
                  </p>
                  <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                    {project.latest_check?.status === 'running' ? (
                      'Check in progress…'
                    ) : project.latest_check ? (
                      <>
                        {project.latest_check.branch && (
                          <>
                            <BranchIcon /> {project.latest_check.branch} ·{' '}
                          </>
                        )}
                        checked {formatRelative(project.latest_check.timestamp)}
                      </>
                    ) : (
                      'Not checked yet'
                    )}
                  </p>
                </button>
                <Button variant="secondary" loading={running} onClick={() => onRunCheck(project.id)}>
                  {running ? 'Running' : 'Run check'}
                </Button>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
