const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers: Record<string, string> = { "Content-Type": "application/json", ...((init?.headers as Record<string, string>) ?? {}) };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (res.status === 401) {
    if (typeof window !== "undefined") {
      localStorage.removeItem("token");
      window.location.href = "/login";
    }
    throw new Error("Unauthorized");
  }
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body?: unknown) => request<T>(path, { method: "PUT", body: body ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

/* ---- Auth ---- */
export interface LoginRequest { username: string; password: string }
export interface LoginResponse { access_token: string; token_type: string; user: { id: number; username: string; role: string } }
export interface RegisterRequest { username: string; password: string; email?: string }

export const authApi = {
  login: (data: LoginRequest) => api.post<LoginResponse>("/api/v1/auth/login", data),
  register: (data: RegisterRequest) => api.post<{ message: string }>("/api/v1/auth/register", data),
  me: () => api.get<{ id: number; username: string; role: string }>("/api/v1/auth/me"),
};

/* ---- Stats ---- */
export interface DashboardStats {
  patient_count: number;
  session_count: number;
  total_duration_seconds: number;
  total_data_size_bytes: number;
  recent_sessions: SessionSummary[];
}

export interface SessionSummary {
  id: number;
  patient_name: string;
  session_name: string;
  created_at: string;
  duration_seconds: number;
  modalities: string[];
}

export const statsApi = {
  dashboard: () => api.get<DashboardStats>("/api/v1/web/stats"),
};

/* ---- Sessions ---- */
export interface SessionListParams { page?: number; page_size?: number; patient_id?: number; modality?: string; date_from?: string; date_to?: string }
export interface PaginatedSessions { items: SessionSummary[]; total: number; page: number; page_size: number }

export interface TimelineSegment { task_name: string; task_type: string; start_sec: number; end_sec: number; color: string }
export interface SessionTimeline { session_id: number; total_duration: number; segments: TimelineSegment[]; modalities: string[] }

export interface WaveformData { modality: string; channels: string[]; sample_rate: number; start_sec: number; end_sec: number; data: number[][] }

export interface ModalityStats { modality: string; sample_rate: number; channels: string[]; duration_seconds: number; file_size_bytes: number }

export interface ParadigmDetail { task_name: string; task_type: string; start_sec: number; end_sec: number; stimuli: StimulusItem[] }
export interface StimulusItem { name: string; type: string; url: string; thumbnail_url?: string }

export const sessionApi = {
  list: (params?: SessionListParams) => {
    const q = new URLSearchParams();
    if (params?.page) q.set("page", String(params.page));
    if (params?.page_size) q.set("page_size", String(params.page_size));
    if (params?.patient_id) q.set("patient_id", String(params.patient_id));
    if (params?.modality) q.set("modality", params.modality);
    if (params?.date_from) q.set("date_from", params.date_from);
    if (params?.date_to) q.set("date_to", params.date_to);
    return api.get<PaginatedSessions>(`/api/v1/web/sessions?${q.toString()}`);
  },
  timeline: (id: number | string) => api.get<SessionTimeline>(`/api/v1/web/sessions/${id}/timeline`),
  waveform: (id: number | string, modality: string, start: number, end: number, channels?: string[]) => {
    const q = new URLSearchParams({ modality, start: String(start), end: String(end) });
    if (channels?.length) q.set("channels", channels.join(","));
    return api.get<WaveformData>(`/api/v1/web/sessions/${id}/waveform?${q.toString()}`);
  },
  modalityStats: (id: number | string, modality: string) => api.get<ModalityStats>(`/api/v1/web/sessions/${id}/modality/${modality}/stats`),
  paradigms: (id: number | string) => api.get<ParadigmDetail[]>(`/api/v1/web/sessions/${id}/paradigms`),
  stimulus: (id: number | string, time: number) => api.get<StimulusItem[]>(`/api/v1/web/sessions/${id}/stimulus?time=${time}`),
  downloadUrl: (id: number | string) => `/api/v1/web/sessions/${id}/download`,
  modalityDownloadUrl: (id: number | string, modality: string) => `/api/v1/web/sessions/${id}/modality/${modality}/download`,
};
