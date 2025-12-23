import { useEffect, useState } from 'react'
import { apiClient } from '../api/client'
import KPICard from '../components/KPICard'
import CO2Trend from '../charts/CO2Trend'
import AnomalyBar from '../charts/AnomalyBar'
import Loading from '../components/Loading'

export default function Dashboard() {
  const [summary, setSummary] = useState(null)
  const [charts, setCharts] = useState(null)
  const [kpis, setKpis] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true)
        const [summaryData, chartsData, kpisData] = await Promise.all([
          apiClient.fetchDashboardSummary(),
          apiClient.fetchDashboardCharts(),
          apiClient.fetchComprehensiveKPIs(),
        ])
        setSummary(summaryData)
        setCharts(chartsData)
        setKpis(kpisData)
        setError(null)
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }

    loadData()
    const interval = setInterval(loadData, 60000) // Refresh every minute
    return () => clearInterval(interval)
  }, [])

  if (loading) return <Loading />
  if (error) return <div className="text-red-600">Error: {error}</div>
  if (!summary || !kpis) return <div className="text-gray-600">No data available</div>

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-600 mt-2">Real-time overview of MRV system performance</p>
      </div>

      {/* Core KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard label="Active Projects" value={kpis.projects} icon="📁" />
        <KPICard 
          label="Tokens Issued" 
          value={kpis.tokens.issued} 
          secondary={`${kpis.tokens.verified_percent}% verified`}
          icon="🎫"
        />
        <KPICard 
          label="Total CO₂ (tCO₂e)" 
          value={kpis.co2.total_reported_tco2e.toFixed(2)} 
          icon="♻️"
        />
        <KPICard 
          label="Anomalies (High)" 
          value={kpis.anomalies.high} 
          secondary={`${kpis.anomalies.total} total`}
          icon="⚠️"
        />
      </div>

      {/* MRV Workflow Status */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">MRV Report Status</h2>
        <div className="grid grid-cols-5 gap-4 text-center">
          <div>
            <div className="text-2xl font-bold text-gray-600">{kpis.mrv.draft}</div>
            <div className="text-sm text-gray-500">Draft</div>
          </div>
          <div className="flex items-center justify-center text-gray-400">→</div>
          <div>
            <div className="text-2xl font-bold text-blue-600">{kpis.mrv.submitted}</div>
            <div className="text-sm text-gray-500">Submitted</div>
          </div>
          <div className="flex items-center justify-center text-gray-400">→</div>
          <div>
            <div className="text-2xl font-bold text-green-600">{kpis.mrv.approved}</div>
            <div className="text-sm text-gray-500">Approved</div>
          </div>
        </div>
        <div className="mt-4 text-center text-sm text-gray-600">
          Approval Rate: <span className="font-semibold">{kpis.mrv.approval_percent}%</span>
        </div>
      </div>

      {/* Charts */}
      {charts && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">CO₂ Trend</h2>
            <CO2Trend data={charts.co2_trend} />
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Anomalies Timeline</h2>
            <AnomalyBar data={charts.anomaly_timeline} />
          </div>
        </div>
      )}

      {/* Detailed KPI Grid */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">Detailed Metrics</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <div>
            <p className="text-gray-600 text-sm">Verified Deliveries</p>
            <p className="text-2xl font-bold text-gray-900">{kpis.deliveries_verified}</p>
          </div>
          <div>
            <p className="text-gray-600 text-sm">MRV Reports</p>
            <p className="text-2xl font-bold text-gray-900">{kpis.mrv.total}</p>
          </div>
          <div>
            <p className="text-gray-600 text-sm">Medium Anomalies</p>
            <p className="text-2xl font-bold text-yellow-600">{kpis.anomalies.medium}</p>
          </div>
          <div>
            <p className="text-gray-600 text-sm">Low Anomalies</p>
            <p className="text-2xl font-bold text-blue-600">{kpis.anomalies.low}</p>
          </div>
          <div>
            <p className="text-gray-600 text-sm">Locked Reports</p>
            <p className="text-2xl font-bold text-green-600">{kpis.mrv.locked}</p>
          </div>
          <div>
            <p className="text-gray-600 text-sm">Last Updated</p>
            <p className="text-sm text-gray-500">{new Date().toLocaleTimeString()}</p>
          </div>
        </div>
      </div>
    </div>
  )
}
