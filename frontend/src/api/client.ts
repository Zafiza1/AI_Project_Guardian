import type {
  CheckCommand,
  DashboardSummary,
  GuardianSettings,
  HealthCheck,
  Project,
  ProjectCreate,
} from '../types';

const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? '/api';

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

function formatDetail(detail: unknown): string {
  if (typeof detail === 'string') return detail;
  // FastAPI validation errors: [{ loc, msg, ... }]
  if (Array.isArray(detail)) {
    return detail
      .map((d) => (typeof d === 'object' && d && 'msg' in d ? String(d.msg).replace(/^Value error, /, '') : String(d)))
      .join('; ');
  }
  return 'Request failed';
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    });
  } catch {
    throw new ApiError('Cannot reach the Guardian backend. Is it running on 127.0.0.1:8000?', 0);
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(body?.detail ? formatDetail(body.detail) : `${response.status} ${response.statusText}`, response.status);
  }
  if (response.status === 204) return undefined as T;
  if (!response.headers.get('content-type')?.includes('application/json')) {
    // Typically the dev server answering with index.html because the /api proxy is not active.
    throw new ApiError(
      `Expected JSON from ${API_BASE_URL}${path} but received ${response.headers.get('content-type') ?? 'unknown content'}. ` +
        'Restart the frontend with "npm run dev" so the /api proxy to the backend is active.',
      response.status,
    );
  }
  return response.json() as Promise<T>;
}

export const api = {
  getDashboard: () => request<DashboardSummary>('/dashboard'),
  getSettings: () => request<GuardianSettings>('/settings'),
  getCheckCommands: () => request<CheckCommand[]>('/check-commands'),

  getProjects: () => request<Project[]>('/projects'),
  getProject: (id: number) => request<Project>(`/projects/${id}`),
  createProject: (data: ProjectCreate) =>
    request<Project>('/projects', { method: 'POST', body: JSON.stringify(data) }),
  deleteProject: (id: number) => request<void>(`/projects/${id}`, { method: 'DELETE' }),

  /** Starts a check in the background; the returned check has status 'running'. */
  runHealthCheck: (projectId: number) =>
    request<HealthCheck>(`/projects/${projectId}/health-check`, { method: 'POST' }),
  getHealthCheck: (checkId: number) => request<HealthCheck>(`/health-checks/${checkId}`),
  getHealthChecks: (projectId: number, limit = 50) =>
    request<HealthCheck[]>(`/projects/${projectId}/health-checks?limit=${limit}`),
};
