export type ApiErrorDetail = {
  error?: string;
  error_code?: string;
  error_type?: string;
  detail?: string;
};

export type ApiErrorBody = {
  detail?: string | ApiErrorDetail;
  error?: string;
  error_code?: string;
  error_type?: string;
};

export type RunCreateResponse = {
  run_id: string;
  status: string;
  diagram_type: string;
};

export type RunSnapshot = {
  run_id: string;
  diagram_type: string;
  status: string;
  current_step?: string | null;
  artifacts?: Record<string, unknown>;
  error?: string | null;
};

export type RunEventPayload = Record<string, any> | undefined;

export type RunEvent = {
  run_id: string;
  ts_ms: number;
  type: string;
  step?: string;
  status?: string;
  payload?: RunEventPayload;
};

export const formatBackendDetail = (detail: unknown): string => {
  if (!detail) return '';
  if (typeof detail === 'string') return detail;
  if (typeof detail === 'object') {
    const d = detail as ApiErrorDetail;
    const code = typeof d.error_code === 'string' ? d.error_code : '';
    const msg = typeof d.error === 'string' ? d.error : '';
    const raw = typeof d.detail === 'string' ? d.detail : '';
    const base = msg || raw || JSON.stringify(detail);
    return code ? `[${code}] ${base}` : base;
  }
  return String(detail);
};

export const extractErrorFromResponse = async (res: Response, fallback: string): Promise<string> => {
  try {
    const j = (await res.json()) as ApiErrorBody;
    const text = formatBackendDetail(j?.detail) || formatBackendDetail(j);
    return text || `${fallback} (${res.status})`;
  } catch {
    return `${fallback} (${res.status})`;
  }
};

export const parseRunEvent = (raw: string): RunEvent => JSON.parse(raw || '{}') as RunEvent;
