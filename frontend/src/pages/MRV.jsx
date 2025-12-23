import { useEffect, useState } from 'react'
import { apiClient } from '../api/client'
import Loading from '../components/Loading'

export default function MRV() {
  const [reports, setReports] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [selectedReportId, setSelectedReportId] = useState(null)
  const [selectedReport, setSelectedReport] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState(null)

  useEffect(() => {
    const loadReports = async () => {
      try {
        setLoading(true)
        const data = await apiClient.fetchMRVReports()
        setReports(Array.isArray(data) ? data : [])
        setError(null)
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }

    loadReports()
  }, [])

  const formatCo2e = (value) => {
    if (value === null || value === undefined) return 'N/A'
    const num = typeof value === 'number' ? value : Number(value)
    if (Number.isFinite(num)) return num.toFixed(2)
    return String(value)
  }

  const openDetails = async (reportId) => {
    try {
      setSelectedReportId(reportId)
      setSelectedReport(null)
      setDetailError(null)
      setDetailLoading(true)
      const data = await apiClient.fetchMRVReport(reportId)
      setSelectedReport(data)
    } catch (err) {
      setDetailError(err?.message || 'Failed to load report')
    } finally {
      setDetailLoading(false)
    }
  }

  const closeDetails = () => {
    setSelectedReportId(null)
    setSelectedReport(null)
    setDetailError(null)
    setDetailLoading(false)
  }

  const getStatusColor = (status) => {
    const colors = {
      DRAFT: 'bg-gray-100 text-gray-800',
      SUBMITTED: 'bg-blue-100 text-blue-800',
      VERIFIED: 'bg-green-100 text-green-800',
      APPROVED: 'bg-indigo-100 text-indigo-800',
      LOCKED: 'bg-green-100 text-green-800',
    }
    return colors[status] || 'bg-gray-100 text-gray-800'
  }

  if (loading) return <Loading />
  if (error) return <div className="text-red-600">Error: {error}</div>

  if (selectedReportId) {
    return (
      <div className="space-y-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">MRV Report Details</h1>
            <p className="text-gray-600 mt-2">Read-only view</p>
          </div>
          <button
            onClick={closeDetails}
            className="px-4 py-2 rounded-md bg-gray-100 text-gray-900 hover:bg-gray-200"
          >
            Back
          </button>
        </div>

        {detailLoading && <Loading />}
        {detailError && !detailLoading && (
          <div className="text-red-600">Error: {detailError}</div>
        )}

        {selectedReport && !detailLoading && (
          <div className="bg-white rounded-lg shadow p-6 space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <div className="text-xs text-gray-500">Report ID</div>
                <div className="font-mono text-sm break-all">{selectedReport.id}</div>
              </div>
              <div>
                <div className="text-xs text-gray-500">Project ID</div>
                <div className="font-mono text-sm break-all">{selectedReport.project_id}</div>
              </div>
              <div>
                <div className="text-xs text-gray-500">Reporting Period</div>
                <div className="text-sm text-gray-900">{selectedReport.reporting_period || '—'}</div>
              </div>
              <div>
                <div className="text-xs text-gray-500">Status</div>
                <div className="text-sm">
                  <span className={`px-3 py-1 rounded-full text-xs font-semibold ${getStatusColor(selectedReport.status)}`}>
                    {selectedReport.status || '—'}
                  </span>
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-500">Total CO₂e (tCO₂e)</div>
                <div className="text-sm font-semibold text-gray-900">{formatCo2e(selectedReport.total_co2e)}</div>
              </div>
              <div>
                <div className="text-xs text-gray-500">Created By</div>
                <div className="text-sm text-gray-900">{selectedReport.created_by || '—'}</div>
              </div>
              <div>
                <div className="text-xs text-gray-500">Verified By</div>
                <div className="text-sm text-gray-900">{selectedReport.verified_by || '—'}</div>
              </div>
              <div>
                <div className="text-xs text-gray-500">Approved By</div>
                <div className="text-sm text-gray-900">{selectedReport.approved_by || '—'}</div>
              </div>
            </div>

            <div className="border-t pt-4 grid gap-4 md:grid-cols-2">
              <div>
                <div className="text-xs text-gray-500">Parameter</div>
                <div className="text-sm text-gray-900">{selectedReport.parameter || '—'}</div>
              </div>
              <div>
                <div className="text-xs text-gray-500">Value</div>
                <div className="text-sm text-gray-900">{selectedReport.value || '—'}</div>
              </div>
              <div className="md:col-span-2">
                <div className="text-xs text-gray-500">Sample Description</div>
                <div className="text-sm text-gray-900 whitespace-pre-wrap">{selectedReport.sample_desc || '—'}</div>
              </div>
            </div>

            <div className="border-t pt-4 grid gap-4 md:grid-cols-2">
              <div>
                <div className="text-xs text-gray-500">Created At</div>
                <div className="text-sm text-gray-900">{selectedReport.created_at || '—'}</div>
              </div>
              <div>
                <div className="text-xs text-gray-500">Updated At</div>
                <div className="text-sm text-gray-900">{selectedReport.updated_at || '—'}</div>
              </div>
              <div>
                <div className="text-xs text-gray-500">Emission Factor Version</div>
                <div className="text-sm text-gray-900">{selectedReport.emission_factor_version_snapshot || '—'}</div>
              </div>
              <div>
                <div className="text-xs text-gray-500">Emission Factor Value</div>
                <div className="text-sm text-gray-900">{selectedReport.emission_factor_value_snapshot ?? '—'}</div>
              </div>
              <div className="md:col-span-2">
                <div className="text-xs text-gray-500">Emission Factor Hash</div>
                <div className="font-mono text-sm break-all">{selectedReport.emission_factor_hash_snapshot || '—'}</div>
              </div>
            </div>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">MRV Reports</h1>
        <p className="text-gray-600 mt-2">Immutable-after-approval workflow with strict state machine</p>
      </div>

      {reports.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-8 text-center">
          <p className="text-gray-600">No MRV reports yet</p>
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase">ID</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase">Period</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase">CO₂e (tCO₂e)</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase">Status</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase">Created By</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-700 uppercase">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {reports.map((report) => (
                <tr key={report.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 text-sm text-gray-600 font-mono">{report.id.slice(0, 8)}...</td>
                  <td className="px-6 py-4 text-sm text-gray-900">{report.reporting_period}</td>
                  <td className="px-6 py-4 text-sm text-gray-900 font-semibold">{formatCo2e(report.total_co2e)}</td>
                  <td className="px-6 py-4 text-sm">
                    <span className={`px-3 py-1 rounded-full text-xs font-semibold ${getStatusColor(report.status)}`}>
                      {report.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">{report.created_by}</td>
                  <td className="px-6 py-4 text-sm">
                    <button
                      className="text-blue-600 hover:text-blue-800 font-medium"
                      onClick={() => openDetails(report.id)}
                    >
                      View Details
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
