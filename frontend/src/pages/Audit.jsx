import { useEffect, useState } from 'react'
import { apiClient } from '../api/client'
import Loading from '../components/Loading'

export default function Audit() {
  const [logs, setLogs] = useState([])
  const [chainValid, setChainValid] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    const loadAuditData = async () => {
      try {
        setLoading(true)
        const [logsData, chainData] = await Promise.all([
          apiClient.fetchAuditLogs(),
          apiClient.verifyAuditChain(),
        ])
        setLogs(Array.isArray(logsData) ? logsData : [])
        setChainValid(chainData.is_valid === true)
        setError(null)
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }

    loadAuditData()
  }, [])

  const getActionColor = (action) => {
    if (action.includes('ISSUED') || action.includes('CREATED')) return 'text-blue-600 bg-blue-50'
    if (action.includes('VERIFIED') || action.includes('APPROVED')) return 'text-green-600 bg-green-50'
    if (action.includes('LOCKED')) return 'text-purple-600 bg-purple-50'
    return 'text-gray-600 bg-gray-50'
  }

  const getActionIcon = (action) => {
    if (action.includes('TOKEN')) return '🎫'
    if (action.includes('DELIVERY')) return '📦'
    if (action.includes('MRV')) return '📋'
    if (action.includes('ANOMALY')) return '⚠️'
    return '📝'
  }

  if (loading) return <Loading />
  if (error) return <div className="text-red-600">Error: {error}</div>

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Audit Trail</h1>
        <p className="text-gray-600 mt-2">Immutable append-only log with hash chaining</p>
      </div>

      {/* Chain Status */}
      <div className="bg-white rounded-lg shadow p-6 border-l-4 border-green-500">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Audit Chain Status</h2>
            <p className="text-sm text-gray-600 mt-1">
              {chainValid === null ? 'Checking...' : chainValid ? '✅ Chain is valid and tamper-proof' : '❌ Chain integrity compromised'}
            </p>
          </div>
          <div className="text-3xl">{chainValid === true ? '✅' : chainValid === false ? '❌' : '⏳'}</div>
        </div>
      </div>

      {/* Audit Logs */}
      {logs.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-8 text-center">
          <p className="text-gray-600">No audit logs yet</p>
        </div>
      ) : (
        <div className="space-y-3">
          {logs.map((log, index) => (
            <div key={log.id} className="bg-white rounded-lg shadow p-4 hover:shadow-md transition-shadow">
              <div className="flex items-start gap-4">
                <span className="text-2xl">{getActionIcon(log.action)}</span>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-1 text-xs font-semibold rounded ${getActionColor(log.action)}`}>
                      {log.action}
                    </span>
                    <span className="text-xs text-gray-500">{log.entity_type}</span>
                  </div>
                  <p className="text-sm text-gray-600 mt-2">
                    Actor: <span className="font-mono text-xs bg-gray-100 px-2 py-1 rounded">{log.actor}</span>
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    {new Date(log.created_at).toLocaleString()} • Entity ID: {log.entity_id?.slice(0, 12)}...
                  </p>
                  {log.event_hash && (
                    <p className="text-xs text-gray-400 mt-2 font-mono truncate">
                      Hash: {log.event_hash.slice(0, 16)}...
                    </p>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
