// Default to Vite dev-server proxy (relative URLs) to avoid CORS issues.
// Can be overridden via VITE_API_BASE_URL or legacy VITE_API_URL.
import { resolveApiBase } from './resolveApiBase'

const API_BASE = resolveApiBase()

function authHeaders() {
  const token = localStorage.getItem('access_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export const apiClient = {
  // Dashboard endpoints
  async fetchDashboardSummary() {
    const res = await fetch(`${API_BASE}/api/v1/dashboard/summary`)
    if (!res.ok) throw new Error(`Failed: ${res.status}`)
    return res.json()
  },

  async fetchDashboardCharts() {
    const res = await fetch(`${API_BASE}/api/v1/dashboard/charts`)
    if (!res.ok) throw new Error(`Failed: ${res.status}`)
    return res.json()
  },

  async fetchComprehensiveKPIs() {
    const res = await fetch(`${API_BASE}/api/v1/dashboard/kpis`)
    if (!res.ok) throw new Error(`Failed: ${res.status}`)
    return res.json()
  },

  // MRV endpoints
  async fetchMRVReports() {
    const res = await fetch(`${API_BASE}/api/v1/mrv-approval/reports`, {
      headers: { ...authHeaders() },
    })
    if (!res.ok) throw new Error(`Failed: ${res.status}`)
    return res.json()
  },

  async fetchMRVReport(reportId) {
    const res = await fetch(`${API_BASE}/api/v1/mrv-approval/reports/${reportId}`, {
      headers: { ...authHeaders() },
    })
    if (!res.ok) throw new Error(`Failed: ${res.status}`)
    return res.json()
  },

  async createMRVReport(payload) {
    const res = await fetch(`${API_BASE}/api/v1/mrv-approval/reports`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(payload),
    })
    if (!res.ok) throw new Error(`Failed: ${res.status}`)
    return res.json()
  },

  async advanceMRVStatus(reportId, nextStatus, actor) {
    const res = await fetch(`${API_BASE}/api/v1/mrv-approval/reports/${reportId}/advance`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ next_status: nextStatus, actor }),
    })
    if (!res.ok) throw new Error(`Failed: ${res.status}`)
    return res.json()
  },

  // Anomaly endpoints
  async fetchAnomalies(projectId) {
    const res = await fetch(`${API_BASE}/api/v1/anomalies/projects/${projectId}`)
    if (!res.ok) throw new Error(`Failed: ${res.status}`)
    return res.json()
  },

  async runAnomalyDetection(tokenUid) {
    const res = await fetch(`${API_BASE}/api/v1/anomalies/run/${tokenUid}`, {
      method: 'POST',
    })
    if (!res.ok) throw new Error(`Failed: ${res.status}`)
    return res.json()
  },

  // Audit endpoints
  async fetchAuditLogs() {
    const res = await fetch(`${API_BASE}/api/v1/audit-logs/`)
    if (!res.ok) throw new Error(`Failed: ${res.status}`)
    return res.json()
  },

  async verifyAuditChain() {
    const res = await fetch(`${API_BASE}/api/v1/audit-logs/verify-chain`)
    if (!res.ok) throw new Error(`Failed: ${res.status}`)
    return res.json()
  },

  // Material token endpoints
  async fetchMaterialTokens(projectId) {
    const res = await fetch(`${API_BASE}/api/v1/material-tokens?project_id=${projectId}`)
    if (!res.ok) throw new Error(`Failed: ${res.status}`)
    return res.json()
  },

  // Delivery endpoints
  async fetchDeliveries(projectId) {
    const res = await fetch(`${API_BASE}/api/v1/deliveries?project_id=${projectId}`)
    if (!res.ok) throw new Error(`Failed: ${res.status}`)
    return res.json()
  },

  // Health check
  async checkHealth() {
    const res = await fetch(`${API_BASE}/health`)
    if (!res.ok) throw new Error(`Failed: ${res.status}`)
    return res.json()
  },
}
