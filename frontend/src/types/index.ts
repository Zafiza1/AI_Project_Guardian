export type CheckStatus = 'running' | 'success' | 'failed' | 'timeout' | 'error';

export interface HealthCheck {
  id: number;
  project_id: number;
  status: CheckStatus;
  branch: string | null;
  is_clean: boolean | null;
  changed_files: number | null;
  check_command: string | null;
  exit_code: number | null;
  duration_ms: number;
  output: string | null;
  error: string | null;
  timestamp: string;
}

export interface Project {
  id: number;
  display_name: string;
  repository_path: string;
  check_command: string | null;
  created_at: string;
  updated_at: string;
  latest_check: HealthCheck | null;
}

export interface ProjectCreate {
  display_name: string;
  repository_path: string;
  check_command: string | null;
}

export interface CheckCommand {
  id: string;
  label: string;
  description: string;
  argv: string[];
}

export interface ProjectCheck {
  project_id: number;
  project_name: string;
  check: HealthCheck | null;
}

export interface DashboardSummary {
  project_count: number;
  check_count: number;
  failed_check_count: number;
  failing_project_count: number;
  latest_checks: ProjectCheck[];
  recent_failures: ProjectCheck[];
}

export interface GuardianSettings {
  read_only: boolean;
  allowed_roots: string[];
  command_timeout_seconds: number;
  max_output_bytes: number;
  max_concurrent_checks: number;
}

export type DiagnosisStatus = 'pending' | 'completed' | 'failed';

export interface DiagnosisFinding {
  problem_summary: string;
  suspected_root_cause: string;
  evidence: string[];
  file_paths: string[];
  line_numbers: string[];
  confidence_level: 'high' | 'medium' | 'low';
  confidence_explanation: string;
  remediation_steps: string[];
  verification_tests: string[];
  missing_information: string[];
  alternative_explanations: string[];
  severity: 'critical' | 'high' | 'medium' | 'low';
  impact_assessment: string;
}

export interface Diagnosis {
  id: number;
  health_check_id: number;
  status: DiagnosisStatus;
  provider: string;
  model: string;
  findings: DiagnosisFinding | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface DiagnosisRequest {
  health_check_id: number;
}
