import { useEffect, useMemo, useState } from 'react'
import { apiClient } from '../api/client'
import Loading from '../components/Loading'

import { Co2TrendChart } from '../charts/Co2TrendChart'
import { MaterialMixChart } from '../charts/MaterialMixChart'
import { DistanceHistogram } from '../charts/DistanceHistogram'
import { SupplierRiskScatter } from '../charts/SupplierRiskScatter'
import { Co2CostScatter } from '../charts/Co2CostScatter'

function toNumber(v) {
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : 0
}

function formatUsd(v) {
  const n = toNumber(v)
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
}

function formatPct(v) {
  const n = toNumber(v)
  return `${n.toFixed(1)}%`
}

export default function Projects() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [projects, setProjects] = useState([])
  const [selectedProjectId, setSelectedProjectId] = useState('')

  const [charts, setCharts] = useState(null)
  const [impact, setImpact] = useState(null)
  const [tokens, setTokens] = useState([])

  useEffect(() => {
    const boot = async () => {
      try {
        setLoading(true)
        setError(null)
        const p = await apiClient.fetchProjects(200)
        setProjects(Array.isArray(p) ? p : [])
        const first = Array.isArray(p) && p.length ? p[0] : null
        setSelectedProjectId(first?.id || '')
      } catch (err) {
        setError(err?.message || 'Failed to load projects')
      } finally {
        setLoading(false)
      }
    }
    boot()
  }, [])

  useEffect(() => {
    const loadProject = async () => {
      if (!selectedProjectId) {
        setCharts(null)
        setImpact(null)
        setTokens([])
        return
      }

      try {
        setLoading(true)
        setError(null)
        const [c, i, t] = await Promise.all([
          apiClient.fetchProjectCharts(selectedProjectId),
          apiClient.fetchProjectImpact(selectedProjectId),
          apiClient.fetchMaterialTokens(selectedProjectId),
        ])

        setCharts(c)
        setImpact(i)
        setTokens(Array.isArray(t) ? t : [])
      } catch (err) {
        setError(err?.message || 'Failed to load project details')
      } finally {
        setLoading(false)
      }
    }

    loadProject()
  }, [selectedProjectId])

  const selectedProject = useMemo(() => projects.find((p) => p.id === selectedProjectId) || null, [projects, selectedProjectId])

  const tokenKpis = useMemo(() => {
    const totalQty = (tokens || []).reduce((acc, t) => acc + toNumber(t.quantity), 0)
    const redeemedQty = (tokens || []).filter((t) => t.redeemed).reduce((acc, t) => acc + toNumber(t.quantity), 0)
    return { totalQty, redeemedQty }
  }, [tokens])

  if (loading && projects.length === 0) return <Loading />

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Projects</h1>
        <p className="text-gray-600 mt-2">Per-project details (dark charts)</p>
      </div>

      {error && <div className="text-red-600">Error: {error}</div>}

      <div className="bg-white rounded-lg shadow p-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="flex flex-col">
          <div className="text-xs text-gray-500">Select project</div>
          <select
            className="mt-1 rounded border border-gray-300 px-3 py-2"
            value={selectedProjectId}
            onChange={(e) => setSelectedProjectId(e.target.value)}
          >
            {projects.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </div>

        {selectedProject && (
          <div className="text-sm text-gray-600">
            <div><span className="text-gray-500">Status:</span> <span className="font-medium">{selectedProject.status}</span></div>
            <div><span className="text-gray-500">Budget:</span> <span className="font-medium">{formatUsd(selectedProject.budget_usd || 0)}</span></div>
          </div>
        )}
      </div>

        {selectedProject && impact && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-white rounded-lg shadow p-4">
              <div className="text-xs text-gray-500">Cost savings (credits value)</div>
              <div className="text-2xl font-bold text-gray-900">{formatUsd(impact.potential_credit_value_usd)}</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
              <div className="text-xs text-gray-500">ROI</div>
              <div className="text-2xl font-bold text-gray-900">{formatPct(impact.roi_pct)}</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
              <div className="text-xs text-gray-500">CO₂ savings (baseline → green)</div>
              <div className="text-2xl font-bold text-gray-900">{toNumber(impact.embodied_co2_savings_t).toFixed(2)} tCO₂e</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
              <div className="text-xs text-gray-500">Carbon credits earned</div>
              <div className="text-2xl font-bold text-gray-900">{toNumber(impact.potential_carbon_credits_t).toFixed(2)} t</div>
          </div>

          <div className="bg-white rounded-lg shadow p-4">
              <div className="text-xs text-gray-500">Lifetime</div>
              <div className="text-2xl font-bold text-gray-900">{impact.lifetime_years} years</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-xs text-gray-500">Baseline CO₂ (normal)</div>
              <div className="text-2xl font-bold text-gray-900">{toNumber(impact.baseline_embodied_co2_t).toFixed(2)} t</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-xs text-gray-500">Green CO₂</div>
              <div className="text-2xl font-bold text-gray-900">{toNumber(impact.green_embodied_co2_t).toFixed(2)} t</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-xs text-gray-500">Tokens redeemed</div>
              <div className="text-2xl font-bold text-gray-900">{tokenKpis.redeemedQty.toFixed(1)} / {tokenKpis.totalQty.toFixed(1)}</div>
          </div>
        </div>
      )}

        {impact && (
          <div className="bg-white rounded-lg shadow p-4 text-xs text-gray-600">
            <div className="font-medium text-gray-900">Methodology</div>
            <div className="mt-1">{impact.methodology_version} • {impact.emission_factor_version}</div>
            <div className="mt-1">{impact.notes}</div>
          </div>
        )}

      {charts && (
        <div className="space-y-6">
          <Co2TrendChart data={charts.co2_trend || []} />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <MaterialMixChart data={charts.material_mix || []} />
            <DistanceHistogram data={charts.distance_histogram || []} />
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <SupplierRiskScatter data={charts.supplier_scatter || []} />
            <Co2CostScatter data={charts.co2_cost_scatter || []} />
          </div>
        </div>
      )}

      {!charts && !loading && (
        <div className="bg-white rounded-lg shadow p-6 text-gray-600">No chart data available.</div>
      )}
    </div>
  )
}
