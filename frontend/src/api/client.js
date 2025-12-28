// Default to Vite dev-server proxy (relative URLs) to avoid CORS issues.
// Can be overridden via VITE_API_BASE_URL or legacy VITE_API_URL.
import { resolveApiBase } from './resolveApiBase'

const API_BASE = resolveApiBase()

function authHeaders() {
  const token = localStorage.getItem('access_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function withAuth(init) {
  return {
    credentials: 'include',
    ...(init || {}),
    headers: {
      ...(init?.headers || {}),
      ...authHeaders(),
    },
  }
}

async function parseOrThrow(res) {
  if (res.ok) return res.json()
  let detail = ''
  try {
    const data = await res.json()
    if (typeof data?.detail === 'string') detail = data.detail
  } catch {
    // ignore
  }
  const msg = detail ? `Failed: ${res.status} - ${detail}` : `Failed: ${res.status}`
  const err = new Error(msg)
  err.status = res.status
  throw err
}

export const apiClient = {
  // Auth endpoints (cookie-based)
  async fetchMe() {
    const res = await fetch(`${API_BASE}/api/v1/auth/me`, withAuth())
    return parseOrThrow(res)
  },

  async login({ email, password }) {
    const res = await fetch(`${API_BASE}/api/v1/auth/login`, withAuth({
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    }))

    const data = await parseOrThrow(res)
    // Backend returns tokens as JSON in addition to setting HttpOnly cookies.
    if (data?.access_token) {
      localStorage.setItem('access_token', data.access_token)
    }
    if (data?.refresh_token) {
      localStorage.setItem('refresh_token', data.refresh_token)
    }
    return data
  },

  async logout() {
    const res = await fetch(`${API_BASE}/api/v1/auth/logout`, withAuth({ method: 'POST' }))
    if (!res.ok && res.status !== 401) throw new Error(`Failed: ${res.status}`)
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
  },

  // Dashboard endpoints
  async fetchDashboardSummary() {
    const res = await fetch(`${API_BASE}/api/v1/dashboard/summary`, withAuth())
    return parseOrThrow(res)
  },

  async fetchCompanyMRVSummary() {
    const res = await fetch(`${API_BASE}/api/v1/mrv/company-summary`, withAuth())
    return parseOrThrow(res)
  },

  async downloadCompliancePackage() {
    const res = await fetch(`${API_BASE}/api/v1/mrv/export/iso?format=zip`, withAuth())
    if (!res.ok) {
      let detail = ''
      try {
        const data = await res.json()
        if (typeof data?.detail === 'string') detail = data.detail
      } catch {
        // ignore
      }
      const msg = detail ? `Failed: ${res.status} - ${detail}` : `Failed: ${res.status}`
      throw new Error(msg)
    }
    return res.blob()
  },

  async fetchProjects(limit = 50) {
    // Use trailing slash to avoid FastAPI redirect (/projects -> /projects/)
    // which can cause auth headers/cookies to be dropped in some clients.
    const res = await fetch(`${API_BASE}/api/v1/projects/?limit=${limit}`, withAuth())
    return parseOrThrow(res)
  },

  async fetchProjectCharts(projectId) {
    const res = await fetch(`${API_BASE}/api/v1/projects/${projectId}/charts`, withAuth())
    return parseOrThrow(res)
  },

  async fetchProjectImpact(projectId) {
    const res = await fetch(`${API_BASE}/api/v1/projects/${projectId}/impact`, withAuth())
    return parseOrThrow(res)
  },

  async fetchDashboardCharts() {
    const res = await fetch(`${API_BASE}/api/v1/dashboard/charts`, withAuth())
    return parseOrThrow(res)
  },

  async fetchComprehensiveKPIs() {
    const res = await fetch(`${API_BASE}/api/v1/dashboard/kpis`, withAuth())
    return parseOrThrow(res)
  },

  // MRV endpoints
  async fetchMRVReports() {
    const res = await fetch(`${API_BASE}/api/v1/mrv-approval/reports`, withAuth())
    return parseOrThrow(res)
  },

  async fetchMRVReport(reportId) {
    const res = await fetch(`${API_BASE}/api/v1/mrv-approval/reports/${reportId}`, withAuth())
    return parseOrThrow(res)
  },

  async createMRVReport(payload) {
    const res = await fetch(`${API_BASE}/api/v1/mrv-approval/reports`, withAuth({
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }))
    return parseOrThrow(res)
  },

  async advanceMRVStatus(reportId, nextStatus) {
    const res = await fetch(`${API_BASE}/api/v1/mrv-approval/reports/${reportId}/advance`, withAuth({
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ next_status: nextStatus }),
    }))
    return parseOrThrow(res)
  },

  // Anomaly endpoints
  async fetchAnomalies(projectId) {
    const res = await fetch(`${API_BASE}/api/v1/anomalies/projects/${projectId}`, withAuth())
    return parseOrThrow(res)
  },

  async runAnomalyDetection(tokenUid) {
    const res = await fetch(`${API_BASE}/api/v1/anomalies/run/${tokenUid}`, withAuth({ method: 'POST' }))
    return parseOrThrow(res)
  },

  // Audit endpoints
  async fetchAuditLogs() {
    const res = await fetch(`${API_BASE}/api/v1/audit-logs/`, withAuth())
    return parseOrThrow(res)
  },

  async verifyAuditChain() {
    const res = await fetch(`${API_BASE}/api/v1/audit-logs/verify-chain`, withAuth())
    return parseOrThrow(res)
  },

  // Material token endpoints
  async fetchMaterialTokens(projectId) {
    const res = await fetch(`${API_BASE}/api/v1/material-tokens/?project_id=${projectId}`, withAuth())
    return parseOrThrow(res)
  },

  async fetchMyMaterialTokens() {
    const res = await fetch(`${API_BASE}/api/v1/material-tokens/`, withAuth())
    return parseOrThrow(res)
  },

  async fetchTokenEvidence(tokenUid) {
    const res = await fetch(`${API_BASE}/api/v1/material-tokens/${tokenUid}/evidence`, withAuth())
    return parseOrThrow(res)
  },

  async uploadEvidenceForToken(tokenUid, evidenceKind, file) {
    const form = new FormData()
    form.append('file', file)

    const qs = new URLSearchParams({ token_uid: tokenUid })
    if (evidenceKind) qs.set('evidence_kind', evidenceKind)

    const res = await fetch(`${API_BASE}/api/v1/upload/evidence?${qs.toString()}`, withAuth({
      method: 'POST',
      body: form,
    }))
    return parseOrThrow(res)
  },

  // Delivery endpoints
  async fetchDeliveries(projectId) {
    const res = await fetch(`${API_BASE}/api/v1/deliveries?project_id=${projectId}`, withAuth())
    return parseOrThrow(res)
  },

  // Health check
  async checkHealth() {
    const res = await fetch(`${API_BASE}/health`, { credentials: 'include' })
    return parseOrThrow(res)
  },
}
