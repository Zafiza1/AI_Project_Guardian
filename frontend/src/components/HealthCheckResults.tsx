import { useState } from 'react';
import type { Diagnosis, HealthCheck } from '../types';
import { formatDuration, formatTimestamp } from '../utils/format';
import { api } from '../api/client';
import { BranchIcon, Button, Card, EmptyState, ErrorBanner, LoadingBlock, StatusBadge, Spinner } from './ui';
import { DiagnosisDetail } from './DiagnosisDetail';

interface HealthCheckResultsProps {
  healthChecks: HealthCheck[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}

function CheckRow({
  check,
  defaultOpen,
  onDiagnose,
}: {
  check: HealthCheck;
  defaultOpen: boolean;
  onDiagnose: (check: HealthCheck) => void;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const canDiagnose = check.status === 'failed' || check.status === 'timeout' || check.status === 'error';

  return (
    <li className="px-4 py-3">
      <button onClick={() => setOpen(!open)} className="flex w-full items-center gap-3 text-left" aria-expanded={open}>
        <span className="w-4 text-slate-400">{open ? '▾' : '▸'}</span>
        <StatusBadge status={check.status} />
        <span className="flex-1 truncate text-sm">
          {formatTimestamp(check.timestamp)}
          {check.branch && (
            <span className="ml-2 text-slate-500 dark:text-slate-400">
              <BranchIcon /> {check.branch}
            </span>
          )}
          {check.is_clean !== null && (
            <span className={`ml-2 text-xs ${check.is_clean ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-600 dark:text-amber-400'}`}>
              {check.is_clean ? 'clean' : `${check.changed_files ?? '?'} changed`}
            </span>
          )}
        </span>
        <span className="shrink-0 text-xs tabular-nums text-slate-500 dark:text-slate-400">
          {check.status === 'running' ? 'in progress' : formatDuration(check.duration_ms)}
        </span>
      </button>

      {open && (
        <div className="mt-3 space-y-2 pl-7">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-slate-600 sm:grid-cols-4 dark:text-slate-300">
            <div>
              <dt className="text-slate-400">Command</dt>
              <dd className="font-mono">{check.check_command ?? 'none'}</dd>
            </div>
            <div>
              <dt className="text-slate-400">Exit code</dt>
              <dd className="font-mono">{check.exit_code ?? '—'}</dd>
            </div>
            <div>
              <dt className="text-slate-400">Duration</dt>
              <dd className="font-mono">{check.status === 'running' ? '—' : formatDuration(check.duration_ms)}</dd>
            </div>
            <div>
              <dt className="text-slate-400">Run ID</dt>
              <dd className="font-mono">#{check.id}</dd>
            </div>
          </dl>
          {check.error && (
            <p className="rounded-md bg-red-50 px-3 py-2 font-mono text-xs text-red-800 dark:bg-red-950/40 dark:text-red-200">
              {check.error}
            </p>
          )}
          {check.output && (
            <pre className="max-h-96 overflow-auto rounded-md bg-slate-950 p-3 font-mono text-xs leading-relaxed text-slate-200">
              {check.output}
            </pre>
          )}
          {canDiagnose && (
            <Button variant="secondary" onClick={() => onDiagnose(check)} className="w-full py-2 text-xs">
              Diagnose with AI
            </Button>
          )}
        </div>
      )}
    </li>
  );
}

export function HealthCheckResults({ healthChecks, loading, error, onRetry }: HealthCheckResultsProps) {
  const [diagnosis, setDiagnosis] = useState<Diagnosis | null>(null);
  const [diagnosisLoading, setDiagnosisLoading] = useState(false);
  const [diagnosisError, setDiagnosisError] = useState<string | null>(null);

  const handleDiagnose = async (check: HealthCheck) => {
    setDiagnosisLoading(true);
    setDiagnosisError(null);
    try {
      const response = await api.requestDiagnosis({ health_check_id: check.id });
      setDiagnosis(response);

      // Poll for completion if pending
      if (response.status === 'pending') {
        const pollInterval = setInterval(async () => {
          try {
            const updated = await api.getDiagnosis(response.id);
            setDiagnosis(updated);
            if (updated.status !== 'pending') {
              clearInterval(pollInterval);
            }
          } catch (e) {
            clearInterval(pollInterval);
            setDiagnosisError('Failed to poll diagnosis status');
          }
        }, 2000);
      }
    } catch (e) {
      setDiagnosisError(e instanceof Error ? e.message : 'Failed to request diagnosis');
    } finally {
      setDiagnosisLoading(false);
    }
  };

  if (diagnosis) {
    return <DiagnosisDetail diagnosis={diagnosis} onClose={() => setDiagnosis(null)} />;
  }

  if (diagnosisLoading) {
    return (
      <Card>
        <div className="flex items-center justify-center p-8">
          <div className="flex items-center gap-3">
            <Spinner />
            <span className="text-sm text-slate-600 dark:text-slate-300">Requesting AI diagnosis...</span>
          </div>
        </div>
      </Card>
    );
  }

  if (diagnosisError) {
    return <ErrorBanner message={diagnosisError} onRetry={() => setDiagnosisError(null)} />;
  }

  if (error) return <ErrorBanner message={error} onRetry={onRetry} />;
  return (
    <Card>
      {loading && healthChecks.length === 0 ? (
        <LoadingBlock label="Loading run history…" />
      ) : healthChecks.length === 0 ? (
        <EmptyState title="No health checks run yet" hint="Click 'Run check' to perform the first one." />
      ) : (
        <ul className="divide-y divide-slate-100 dark:divide-slate-800">
          {healthChecks.map((check, i) => (
            <CheckRow key={check.id} check={check} defaultOpen={i === 0} onDiagnose={handleDiagnose} />
          ))}
        </ul>
      )}
    </Card>
  );
}
