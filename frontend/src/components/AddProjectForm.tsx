import { useState } from 'react';
import { api } from '../api/client';
import type { CheckCommand, GuardianSettings, Project } from '../types';
import { Button, Card, ErrorBanner } from './ui';

interface AddProjectFormProps {
  checkCommands: CheckCommand[];
  settings: GuardianSettings | null;
  onProjectAdded: (project: Project) => void;
}

const inputClass =
  'block w-full rounded-md border-0 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm ring-1 ring-inset ring-slate-300 placeholder:text-slate-400 focus:ring-2 focus:ring-inset focus:ring-indigo-600 dark:bg-slate-950 dark:text-white dark:ring-slate-700';

export function AddProjectForm({ checkCommands, settings, onProjectAdded }: AddProjectFormProps) {
  const [displayName, setDisplayName] = useState('');
  const [repositoryPath, setRepositoryPath] = useState('');
  const [checkCommand, setCheckCommand] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const selected = checkCommands.find((c) => c.id === checkCommand);
  const noRoots = settings !== null && settings.allowed_roots.length === 0;

  const handleSubmit = async (e: { preventDefault: () => void }) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      const project = await api.createProject({
        display_name: displayName.trim(),
        repository_path: repositoryPath.trim(),
        check_command: checkCommand || null,
      });
      setDisplayName('');
      setRepositoryPath('');
      setCheckCommand('');
      setSuccess(`Registered "${project.display_name}".`);
      onProjectAdded(project);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to register project');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card className="p-5">
      <h2 className="text-base font-semibold">Register a repository</h2>
      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
        Guardian only reads the repository. It never modifies, commits, or pushes.
      </p>

      {settings && (
        <div className="mt-3 rounded-md bg-slate-50 px-3 py-2 text-xs text-slate-600 dark:bg-slate-800/60 dark:text-slate-300">
          {noRoots ? (
            <span className="text-amber-700 dark:text-amber-300">
              No permitted directories are configured. Set <code className="font-mono">GUARDIAN_ALLOWED_ROOTS</code> in{' '}
              <code className="font-mono">backend/.env</code> and restart the backend.
            </span>
          ) : (
            <>
              <p className="font-medium">Permitted directories ({settings.allowed_roots.length}):</p>
              <ul className="mt-1.5 flex flex-wrap gap-1.5">
                {settings.allowed_roots.map((r) => (
                  <li key={r}>
                    <code className="inline-block rounded border border-slate-200 bg-white px-1.5 py-0.5 font-mono dark:border-slate-700 dark:bg-slate-900">
                      {r}
                    </code>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}

      <form onSubmit={handleSubmit} className="mt-4 space-y-4">
        <div>
          <label htmlFor="display_name" className="mb-1 block text-sm font-medium">
            Display name
          </label>
          <input
            id="display_name"
            className={inputClass}
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            maxLength={255}
            placeholder="My service"
            required
          />
        </div>

        <div>
          <label htmlFor="repository_path" className="mb-1 block text-sm font-medium">
            Local repository path
          </label>
          <input
            id="repository_path"
            className={`${inputClass} font-mono`}
            value={repositoryPath}
            onChange={(e) => setRepositoryPath(e.target.value)}
            placeholder={settings?.allowed_roots[0] ? `${settings.allowed_roots[0]}\\my-repo` : 'D:\\Projects\\my-repo'}
            required
            spellCheck={false}
          />
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">Absolute path to the root of a Git repository.</p>
        </div>

        <div>
          <label htmlFor="check_command" className="mb-1 block text-sm font-medium">
            Check command
          </label>
          <select
            id="check_command"
            className={inputClass}
            value={checkCommand}
            onChange={(e) => setCheckCommand(e.target.value)}
          >
            <option value="">None (Git checks only)</option>
            {checkCommands.map((c) => (
              <option key={c.id} value={c.id}>
                {c.label}
              </option>
            ))}
          </select>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            {selected ? (
              <>
                {selected.description} Runs <code className="font-mono">{selected.argv.join(' ')}</code>
                {settings && ` with a ${settings.command_timeout_seconds}s timeout`}.
              </>
            ) : (
              'Only allowlisted commands can be run. Arbitrary shell commands are not supported.'
            )}
          </p>
        </div>

        {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}
        {success && <p className="text-sm text-emerald-700 dark:text-emerald-400">{success}</p>}

        <Button type="submit" loading={submitting} className="w-full">
          {submitting ? 'Validating…' : 'Register project'}
        </Button>
      </form>
    </Card>
  );
}
