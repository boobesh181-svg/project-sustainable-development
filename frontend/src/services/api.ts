import axios, { AxiosResponse, AxiosError } from 'axios';
import { resolveApiBase } from '../api/resolveApiBase';

// Default to Vite dev-server proxy (relative URLs) to avoid CORS issues.
// Can be overridden via VITE_API_BASE_URL or legacy VITE_API_URL.
const API_BASE = resolveApiBase();

// Create axios instance with default config
export const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 10000,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add response interceptor to handle auth errors
apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Token expired or invalid: avoid redirect loops on boot.
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export interface DashboardSummary {
  // 1. Active Projects
  active_projects: number;
  // 2. Total CO₂ Saved (tCO₂e)
  total_co2_saved_t: number;
  // 3. Estimated Embodied CO₂
  estimated_embodied_co2_t: number;
  // 4. Operational CO₂ (yearly)
  operational_co2_yearly_t: number;
  // 5. Material Tokens Issued (month)
  material_tokens_issued_month: number;
  // 6. Tokens Redeemed (%)
  tokens_redeemed_pct: number;
  // 7. Open Anomalies
  open_anomalies: number;
  // 8. Open Whistleblower Cases
  open_whistleblower_cases: number;
  // 9. Avg Delivery Geotag Distance (meters)
  avg_delivery_distance_m: number;
  // 10. Low-carbon Material Fraction (%)
  low_carbon_material_fraction_pct: number;
  // 11. Supplier Money Saved
  supplier_money_saved_usd: number;
  // 12. Project Budget Utilization (%)
  project_budget_utilization_pct: number;
}

export async function fetchDashboardSummary(): Promise<DashboardSummary> {
  const res = await fetch(`${API_BASE}/api/v1/dashboard/summary`, { credentials: 'include' });
  if (!res.ok) {
    throw new Error(`Failed to fetch dashboard summary: ${res.status}`);
  }
  return res.json();
}

// Charts types mirror backend DashboardCharts schema (simplified for frontend use)
export interface Co2TrendPoint {
  month: string;
  embodied: number;
  operational: number;
  saved: number;
}

export interface MaterialMixSlice {
  material_type: string;
  qty: number;
}

export interface AnomalyTimelinePoint {
  date: string;
  count: number;
}

export interface DistanceBucket {
  bucket_label: string;
  count: number;
}

export interface SupplierScatterPoint {
  supplier: string;
  total_value: number;
  project_count: number;
}

export interface Co2CostPoint {
  project_name: string;
  co2_t: number;
  cost_usd: number;
}

export interface DashboardCharts {
  co2_trend: Co2TrendPoint[];
  material_mix: MaterialMixSlice[];
  anomaly_timeline: AnomalyTimelinePoint[];
  distance_histogram: DistanceBucket[];
  supplier_scatter: SupplierScatterPoint[];
  co2_cost_scatter: Co2CostPoint[];
}

export async function fetchDashboardCharts(): Promise<DashboardCharts> {
  const res = await fetch(`${API_BASE}/api/v1/dashboard/charts`, { credentials: 'include' });
  if (!res.ok) {
    throw new Error(`Failed to fetch dashboard charts: ${res.status}`);
  }
  return res.json();
}

export interface HealthStatus {
  status: string;
  db: boolean;
  mode: 'demo' | 'prod';
}

export async function fetchHealth(): Promise<HealthStatus> {
  const res = await fetch(`${API_BASE}/health`, { credentials: 'include' });
  if (!res.ok) {
    throw new Error(`Failed to fetch health: ${res.status}`);
  }
  return res.json();
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type?: string;
}

export interface UserMe {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  role: string;
  created_at?: string | null;
  updated_at?: string | null;
}

export async function login(email: string, password: string): Promise<TokenPair> {
  const res = await apiClient.post<TokenPair>('/api/v1/auth/login', { email, password });
  // Browser auth uses HttpOnly cookies set by the backend.
  return res.data;
}

export async function logout(): Promise<void> {
  await apiClient.post('/api/v1/auth/logout');
}

export async function fetchMe(): Promise<UserMe> {
  const res = await apiClient.get<UserMe>('/api/v1/auth/me');
  return res.data;
}

export interface Project {
  id: string;
  name: string;
  status: string;
  lat: number;
  lon: number;
  budget_usd?: number | null;
  pilot?: boolean;
  created_by: string;
  created_at: string;
}

export async function fetchProjects(limit = 200): Promise<Project[]> {
  // Use trailing slash to avoid FastAPI redirect (/projects -> /projects/)
  const res = await apiClient.get<Project[]>('/api/v1/projects/', { params: { limit } });
  return res.data;
}

export interface MRVReportSummary {
  id: string;
  project_id: string;
  reporting_period: string;
  total_co2e: number;
  status: string;
  created_by: string;
  created_at: string;
  pilot?: boolean;
}

export interface MRVReportCreate {
  project_id: string;
  reporting_period: string;
  sample_desc: string;
  parameter: string;
  value: string;
  total_co2e: number;
  emission_factor_id?: string | null;
  certificate_path?: string | null;
}

export interface MRVReportOut {
  id: string;
  project_id: string;
  reporting_period: string;
  sample_desc: string;
  parameter: string;
  value: string;
  total_co2e: number;
  status: string;
  created_by: string;
  verified_by: string | null;
  approved_by: string | null;
  created_at: string;
  updated_at: string;
  emission_factor_id: string | null;
  certificate_path: string | null;
  emission_factor_version_snapshot: string | null;
  emission_factor_hash_snapshot: string | null;
  emission_factor_value_snapshot: number | null;
  pilot?: boolean;
}

export async function fetchReports(params?: {
  project_id?: string;
  status?: string;
  limit?: number;
}): Promise<MRVReportSummary[]> {
  const res = await apiClient.get<MRVReportSummary[]>('/api/v1/mrv-approval/reports', { params });
  return res.data;
}

export async function createReport(payload: MRVReportCreate): Promise<MRVReportOut> {
  const res = await apiClient.post<MRVReportOut>('/api/v1/mrv-approval/reports', payload);
  return res.data;
}

export async function advanceReport(reportId: string, nextStatus: 'SUBMITTED' | 'VERIFIED' | 'APPROVED' | 'LOCKED'): Promise<MRVReportOut> {
  const res = await apiClient.post<MRVReportOut>(`/api/v1/mrv-approval/reports/${reportId}/advance`, {
    next_status: nextStatus,
  });
  return res.data;
}

export async function downloadComplianceBundle(reportId: string): Promise<Blob> {
  const res = await fetch(`${API_BASE}/api/v1/mrv/export/${reportId}`, {
    credentials: 'include',
  });
  if (!res.ok) {
    throw new Error(`Failed to export compliance bundle: ${res.status}`);
  }
  return res.blob();
}

// ---------------- Acknowledgements ----------------

export type DeliveryChannel = 'in_app' | 'email' | 'webhook';
export type AckResponseType = 'acknowledge' | 'comment' | 'dispute';

export interface NotificationOut {
  id: string;
  activity_id: string;
  notified_user_id: string;
  notification_timestamp: string;
  response_deadline_timestamp: string;
  delivery_channel: DeliveryChannel;
  demo_watermark: boolean;
  seconds_remaining?: number | null;
}

export interface ResponseOut {
  id: string;
  notification_id: string;
  responder_user_id: string | null;
  response_type: string;
  response_timestamp: string;
  response_comment: string | null;
  demo_watermark: boolean;
}

export interface AcknowledgementStatusOut {
  activity_id: string;
  derived_status: 'UNSEEN' | 'SEEN' | 'ACKNOWLEDGED' | 'DISPUTED' | 'DEEMED_OBSERVED';
  computed_at: string;
  notifications: Array<{
    notification: NotificationOut;
    responses: ResponseOut[];
  }>;
}

export interface ProjectAcknowledgementSummaryOut {
  project_id: string;
  derived_status: string;
  disputed_count: number;
  acknowledged_count: number;
  deemed_observed_count: number;
  unseen_count: number;
  computed_at: string;
}

export async function fetchPendingNotifications(limit = 50): Promise<NotificationOut[]> {
  const res = await apiClient.get<NotificationOut[]>('/api/v1/notifications/pending', { params: { limit } });
  return res.data;
}

export async function respondToNotification(notificationId: string, payload: { response_type: AckResponseType; response_comment?: string | null; }): Promise<ResponseOut> {
  const res = await apiClient.post<ResponseOut>(`/api/v1/notifications/${notificationId}/respond`, payload);
  return res.data;
}

export async function fetchAcknowledgementStatus(activityId: string): Promise<AcknowledgementStatusOut> {
  const res = await apiClient.get<AcknowledgementStatusOut>(`/api/v1/events/${activityId}/acknowledgement-status`);
  return res.data;
}

export async function fetchProjectAcknowledgementSummary(projectId: string): Promise<ProjectAcknowledgementSummaryOut> {
  const res = await apiClient.get<ProjectAcknowledgementSummaryOut>(`/api/v1/ack/projects/${projectId}/summary`);
  return res.data;
}
