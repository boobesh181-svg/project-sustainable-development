import { useEffect, useMemo, useState } from 'react'
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip, BarChart, Bar, XAxis, YAxis, CartesianGrid } from 'recharts'
import Loading from '../components/Loading'
import { apiClient } from '../api/client'

const COLORS = ["#22c55e", "#38bdf8", "#f97316", "#a855f7", "#e11d48", "#facc15"]

function toNumber(v) {
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : 0
}

function formatPct(v) {
  return `${toNumber(v).toFixed(1)}%`
}

function formatT(v) {
  return `${toNumber(v).toFixed(2)} tCO₂e`
}

function Badge({ label, pct }) {
  return (
    <div className="inline-flex items-center gap-2 rounded-full bg-gray-100 px-3 py-1 text-xs text-gray-700">
      <span className="font-medium">{label}</span>
      <span className="text-gray-500">{formatPct(pct)}</span>
    </div>
  )
}

export default function CompanyOverview() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [data, setData] = useState(null)
  const [downloading, setDownloading] = useState(false)

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true)
        setError(null)
        const summary = await apiClient.fetchCompanyMRVSummary()
        setData(summary)
      } catch (err) {
        setError(err?.message || 'Failed to load company summary')
        setData(null)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const materialPie = useMemo(() => {
    const rows = data?.emissions_by_material || []
    return rows
      .filter((r) => toNumber(r.emissions_tco2e) > 0)
      .map((r) => ({ name: r.material_name || r.material_code, value: toNumber(r.emissions_tco2e) }))
  }, [data])

  const supplierBars = useMemo(() => {
    const rows = data?.emissions_by_supplier || []
    return rows
      .slice(0, 10)
      .map((r) => ({ name: r.supplier_name, emissions: toNumber(r.emissions_tco2e) }))
  }, [data])

  if (loading && !data) return <Loading />

  const downloadCompliance = async () => {
    setDownloading(true)
    setError(null)
    try {
      const blob = await apiClient.downloadCompliancePackage()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `mrv_compliance_package_${new Date().toISOString().replace(/[:.]/g, '-')}.zip`
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      setError(err?.message || 'Failed to download compliance package')
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Company MRV Overview</h1>
        <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
          <p className="text-gray-600">Business-ready snapshot of tracked emissions and compliance status.</p>
          <button
            type="button"
            onClick={downloadCompliance}
            disabled={downloading}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded hover:bg-blue-700 disabled:opacity-50"
          >
            {downloading ? 'Preparing…' : 'Download Compliance Package'}
          </button>
        </div>
      </div>

      {error && <div className="text-red-600">Error: {error}</div>}

      {data && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white rounded-lg shadow p-4">
              <div className="text-xs text-gray-500">Total emissions</div>
              <div className="text-2xl font-bold text-gray-900">{formatT(data.total_emissions_tco2e)}</div>
              <div className="mt-2 flex flex-wrap gap-2">
                <Badge label="Verified" pct={data.pct_verified} />
                <Badge label="Approved" pct={data.pct_approved} />
                <Badge label="Locked" pct={data.pct_locked} />
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-4">
              <div className="text-xs text-gray-500">Reporting window</div>
              <div className="text-sm font-medium text-gray-900 mt-1">
                {data.reporting_period_start ? new Date(data.reporting_period_start).toLocaleDateString() : '—'}
                {' '}→{' '}
                {data.reporting_period_end ? new Date(data.reporting_period_end).toLocaleDateString() : '—'}
              </div>
              <div className="text-xs text-gray-500 mt-2">Methodology</div>
              <div className="text-sm text-gray-900">{data.methodology_version}</div>
            </div>

            <div className="bg-white rounded-lg shadow p-4">
              <div className="text-xs text-gray-500">Emission factor sources</div>
              <div className="text-2xl font-bold text-gray-900">{(data.emission_factor_sources_used || []).length}</div>
              <div className="text-xs text-gray-500 mt-2">Active factors used in calculations</div>
            </div>

            <div className="bg-white rounded-lg shadow p-4">
              <div className="text-xs text-gray-500">MRV reports</div>
              <div className="text-2xl font-bold text-gray-900">{(data.reports_by_status || []).reduce((a, r) => a + (r.count || 0), 0)}</div>
              <div className="text-xs text-gray-500 mt-2">Status distribution below</div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <h2 className="mb-3 text-sm font-semibold text-slate-200">Material emissions split</h2>
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={materialPie} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={90}>
                      {materialPie.map((entry, idx) => (
                        <Cell key={entry.name} fill={COLORS[idx % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{ backgroundColor: '#020617', borderColor: '#1e293b', fontSize: 12 }}
                      formatter={(v) => `${toNumber(v).toFixed(2)} tCO₂e`}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <h2 className="mb-3 text-sm font-semibold text-slate-200">Supplier emissions (top 10)</h2>
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={supplierBars} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                    <CartesianGrid stroke="#1f2937" strokeDasharray="3 3" />
                    <XAxis dataKey="name" tick={{ fill: '#cbd5e1', fontSize: 11 }} interval={0} angle={-20} height={60} />
                    <YAxis tick={{ fill: '#cbd5e1', fontSize: 11 }} />
                    <Tooltip contentStyle={{ backgroundColor: '#020617', borderColor: '#1e293b', fontSize: 12 }} />
                    <Bar dataKey="emissions" fill={COLORS[1]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-sm font-semibold text-gray-900">MRV status</div>
            <div className="mt-3 flex flex-wrap gap-2">
              {(data.reports_by_status || []).map((s) => (
                <div key={s.status} className="rounded-full border px-3 py-1 text-xs text-gray-700">
                  <span className="font-medium">{s.status}</span>
                  <span className="text-gray-500"> · {s.count} · {formatPct(s.pct)}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-sm font-semibold text-gray-900">Why this system exists</div>
            <div className="mt-2 space-y-2 text-sm text-gray-700">
              <p>
                Construction MRV only works when numbers can be reproduced, roles are separated, and every decision is
                traceable.
              </p>
              <ul className="list-disc pl-5 space-y-1">
                <li>
                  <span className="font-medium">Reproducibility:</span> CO₂ calculations reference versioned emission
                  factors and snapshots.
                </li>
                <li>
                  <span className="font-medium">Separation of duties:</span> issuer ≠ verifier ≠ approver.
                </li>
                <li>
                  <span className="font-medium">Auditability:</span> append-only audit logs and immutable lifecycle
                  rules after locking/retirement.
                </li>
                <li>
                  <span className="font-medium">Review-ready exports:</span> one-click compliance package for external
                  review.
                </li>
              </ul>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
