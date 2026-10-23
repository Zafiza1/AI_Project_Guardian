import type { Diagnosis } from '../types';
import { formatTimestamp } from '../utils/format';
import { Card, SectionTitle, StatusBadge, Spinner } from './ui';

interface DiagnosisDetailProps {
  diagnosis: Diagnosis;
  onClose: () => void;
}

export function DiagnosisDetail({ diagnosis, onClose }: DiagnosisDetailProps) {
  const { findings, error_message } = diagnosis;

  return (
    <div className="space-y-4">
      <Card className="p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-semibold">AI Diagnosis</h2>
              <StatusBadge status={diagnosis.status} />
            </div>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              {diagnosis.provider} / {diagnosis.model} • {formatTimestamp(diagnosis.created_at)}
            </p>
          </div>
          <button onClick={onClose} className="rounded px-2 py-1 text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800">
            ✕
          </button>
        </div>
      </Card>

      {diagnosis.status === 'pending' && (
        <Card>
          <div className="flex items-center gap-3 p-4">
            <Spinner />
            <p className="text-sm text-slate-600 dark:text-slate-300">Diagnosis in progress...</p>
          </div>
        </Card>
      )}

      {diagnosis.status === 'failed' && (
        <Card className="border-red-200 bg-red-50 dark:border-red-900/50 dark:bg-red-950/20">
          <div className="p-4">
            <h3 className="font-semibold text-red-900 dark:text-red-200">Diagnosis Failed</h3>
            <p className="mt-1 text-sm text-red-800 dark:text-red-300">{error_message || 'Unknown error'}</p>
          </div>
        </Card>
      )}

      {diagnosis.status === 'completed' && findings && (
        <div className="space-y-4">
          <Card className="p-5">
            <SectionTitle>Problem Summary</SectionTitle>
            <p className="mt-2 text-sm text-slate-700 dark:text-slate-300">{findings.problem_summary}</p>
          </Card>

          <Card className="p-5">
            <SectionTitle>Suspected Root Cause</SectionTitle>
            <p className="mt-2 text-sm text-slate-700 dark:text-slate-300">{findings.suspected_root_cause}</p>
          </Card>

          {findings.evidence.length > 0 && (
            <Card className="p-5">
              <SectionTitle>Evidence</SectionTitle>
              <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-slate-700 dark:text-slate-300">
                {findings.evidence.map((evidence, i) => (
                  <li key={i}>{evidence}</li>
                ))}
              </ul>
            </Card>
          )}

          {(findings.file_paths.length > 0 || findings.line_numbers.length > 0) && (
            <Card className="p-5">
              <SectionTitle>References</SectionTitle>
              <div className="mt-2 space-y-2 text-sm">
                {findings.file_paths.length > 0 && (
                  <div>
                    <dt className="text-xs text-slate-500 dark:text-slate-400">File paths</dt>
                    <dd className="mt-1 font-mono text-slate-700 dark:text-slate-300">
                      {findings.file_paths.join(', ') || 'None'}
                    </dd>
                  </div>
                )}
                {findings.line_numbers.length > 0 && (
                  <div>
                    <dt className="text-xs text-slate-500 dark:text-slate-400">Line numbers</dt>
                    <dd className="mt-1 font-mono text-slate-700 dark:text-slate-300">
                      {findings.line_numbers.join(', ') || 'None'}
                    </dd>
                  </div>
                )}
              </div>
            </Card>
          )}

          <Card className="p-5">
            <SectionTitle>Confidence Assessment</SectionTitle>
            <div className="mt-2 flex items-center gap-2">
              <span
                className={`rounded px-2 py-0.5 text-xs font-medium ${
                  findings.confidence_level === 'high'
                    ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300'
                    : findings.confidence_level === 'medium'
                      ? 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300'
                      : 'bg-slate-100 text-slate-800 dark:bg-slate-700 dark:text-slate-300'
                }`}
              >
                {findings.confidence_level.toUpperCase()}
              </span>
              <span className="text-sm text-slate-600 dark:text-slate-400">{findings.confidence_explanation}</span>
            </div>
          </Card>

          <Card className="p-5">
            <SectionTitle>Severity & Impact</SectionTitle>
            <div className="mt-2 space-y-2 text-sm">
              <div>
                <dt className="text-xs text-slate-500 dark:text-slate-400">Severity</dt>
                <dd
                  className={`mt-1 font-medium ${
                    findings.severity === 'critical'
                      ? 'text-red-700 dark:text-red-400'
                      : findings.severity === 'high'
                        ? 'text-orange-700 dark:text-orange-400'
                        : findings.severity === 'medium'
                          ? 'text-amber-700 dark:text-amber-400'
                          : 'text-slate-700 dark:text-slate-400'
                  }`}
                >
                  {findings.severity.toUpperCase()}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-slate-500 dark:text-slate-400">Impact</dt>
                <dd className="mt-1 text-slate-700 dark:text-slate-300">{findings.impact_assessment}</dd>
              </div>
            </div>
          </Card>

          {findings.remediation_steps.length > 0 && (
            <Card className="p-5">
              <SectionTitle>Recommended Remediation</SectionTitle>
              <ol className="mt-2 list-inside list-decimal space-y-2 text-sm text-slate-700 dark:text-slate-300">
                {findings.remediation_steps.map((step, i) => (
                  <li key={i}>{step}</li>
                ))}
              </ol>
            </Card>
          )}

          {findings.verification_tests.length > 0 && (
            <Card className="p-5">
              <SectionTitle>Verification Tests</SectionTitle>
              <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-slate-700 dark:text-slate-300">
                {findings.verification_tests.map((test, i) => (
                  <li key={i}>{test}</li>
                ))}
              </ul>
            </Card>
          )}

          {findings.missing_information.length > 0 && (
            <Card className="p-5 border-amber-200 bg-amber-50 dark:border-amber-900/50 dark:bg-amber-950/20">
              <SectionTitle>Missing Information</SectionTitle>
              <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-amber-900 dark:text-amber-200">
                {findings.missing_information.map((info, i) => (
                  <li key={i}>{info}</li>
                ))}
              </ul>
            </Card>
          )}

          {findings.alternative_explanations.length > 0 && (
            <Card className="p-5">
              <SectionTitle>Alternative Explanations</SectionTitle>
              <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-slate-700 dark:text-slate-300">
                {findings.alternative_explanations.map((alt, i) => (
                  <li key={i}>{alt}</li>
                ))}
              </ul>
            </Card>
          )}

          <Card className="border-slate-200 bg-slate-50 p-4 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-900/50 dark:text-slate-400">
            <p>
              <strong>Note:</strong> This diagnosis is an AI-generated hypothesis based on the available evidence. The AI
              may not have complete context. Always verify recommendations before applying them to your project.
            </p>
          </Card>
        </div>
      )}
    </div>
  );
}
