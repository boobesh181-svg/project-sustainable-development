import { useEffect, useState } from 'react'
import { apiClient } from '../api/client'
import Loading from '../components/Loading'

export default function Anomalies() {
  const [anomalies, setAnomalies] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [projectId, setProjectId] = useState(null)
  const [acknowledgedIds, setAcknowledgedIds] = useState(() => new Set())

  useEffect(() => {
    const loadAnomalies = async () => {
      try {
        setLoading(true)
        const projects = await apiClient.fetchProjects(1)
        const first = Array.isArray(projects) ? projects[0] : null
        if (!first?.id) {
          setProjectId(null)
          setAnomalies([])
          setError(null)
          return
        }

        setProjectId(first.id)
        const data = await apiClient.fetchAnomalies(first.id)
        setAnomalies(Array.isArray(data) ? data : [])
        setError(null)
      } catch (err) {
        setError(err?.message || 'Failed to load anomalies')
        setAnomalies([])
      } finally {
        setLoading(false)
      }
    }

    loadAnomalies()
  }, [])

  const getSeverityColor = (severity) => {
    const colors = {
      HIGH: 'bg-red-100 text-red-800 border-red-300',
      MEDIUM: 'bg-yellow-100 text-yellow-800 border-yellow-300',
      LOW: 'bg-blue-100 text-blue-800 border-blue-300',
    }
    return colors[severity] || 'bg-gray-100 text-gray-800'
  }

  const acknowledge = (id) => {
    setAcknowledgedIds((prev) => {
      const next = new Set(prev)
      next.add(id)
      return next
    })
  }

  if (loading) return <Loading />
  if (error) return <div className="text-red-600">Error: {error}</div>

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Anomaly Detection</h1>
        <p className="text-gray-600 mt-2">Automated rules engine detects suspicious patterns</p>
        {projectId && <p className="text-xs text-gray-500 mt-1">Project: {projectId}</p>}
      </div>

      {anomalies.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-8 text-center">
          <p className="text-gray-600">✅ No anomalies detected</p>
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50 text-gray-700">
              <tr>
                <th className="text-left font-semibold px-4 py-3">Rule</th>
                <th className="text-left font-semibold px-4 py-3">Severity</th>
                <th className="text-left font-semibold px-4 py-3">Why Flagged</th>
                <th className="text-left font-semibold px-4 py-3">Explanation</th>
                <th className="text-left font-semibold px-4 py-3">Detected</th>
                <th className="text-left font-semibold px-4 py-3">Acknowledge</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {anomalies.map((anomaly) => {
                const acknowledged = acknowledgedIds.has(anomaly.id)
                const rule = anomaly.rule_id || anomaly.rule_code || '—'
                return (
                  <tr key={anomaly.id} className={anomaly.requires_action ? 'bg-red-50/50' : ''}>
                    <td className="px-4 py-3 text-gray-900 font-medium whitespace-nowrap">{rule}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded border ${getSeverityColor(anomaly.severity)}`}>
                        {anomaly.severity || '—'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-700">{anomaly.description || '—'}</td>
                    <td className="px-4 py-3 text-gray-700">{anomaly.explanation || '—'}</td>
                    <td className="px-4 py-3 text-gray-600 whitespace-nowrap">
                      {anomaly.detected_at ? new Date(anomaly.detected_at).toLocaleString() : '—'}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        onClick={() => acknowledge(anomaly.id)}
                        disabled={acknowledged}
                        className={
                          acknowledged
                            ? 'px-3 py-1.5 rounded bg-gray-100 text-gray-400 cursor-not-allowed'
                            : 'px-3 py-1.5 rounded bg-blue-600 text-white hover:bg-blue-700'
                        }
                      >
                        {acknowledged ? 'Acknowledged' : 'Acknowledge'}
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
