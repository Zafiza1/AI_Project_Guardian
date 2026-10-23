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
