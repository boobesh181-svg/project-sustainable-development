import { useEffect, useMemo, useState } from 'react'
import { apiClient } from '../api/client'

function statusFromEvidence(evidenceList) {
  const latest = evidenceList?.[0]
  if (!latest) return { label: 'No evidence', tone: 'bg-gray-100 text-gray-700' }
  if (!latest.verified_at) return { label: 'Pending review', tone: 'bg-yellow-100 text-yellow-800' }

  const decision = (latest.decision || '').toLowerCase()
  if (decision === 'accepted') return { label: 'Accepted', tone: 'bg-green-100 text-green-800' }
  if (decision === 'rejected') return { label: 'Rejected', tone: 'bg-red-100 text-red-800' }
  if (decision === 'needs_correction') return { label: 'Needs correction', tone: 'bg-orange-100 text-orange-800' }
  return { label: 'Verified', tone: 'bg-blue-100 text-blue-800' }
}

export default function SupplierPortal() {
  const [tokens, setTokens] = useState([])
  const [evidenceByToken, setEvidenceByToken] = useState({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [selectedTokenUid, setSelectedTokenUid] = useState('')
  const [evidenceKind, setEvidenceKind] = useState('invoice')
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [message, setMessage] = useState('')

  const tokenOptions = useMemo(() => tokens.map((t) => t.token_uid), [tokens])

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      setError('')
      try {
        const list = await apiClient.fetchMyMaterialTokens()
        setTokens(list)
        if (list.length > 0) setSelectedTokenUid(list[0].token_uid)

        const pairs = await Promise.all(
          list.map(async (t) => {
            try {
              const ev = await apiClient.fetchTokenEvidence(t.token_uid)
              return [t.token_uid, ev]
            } catch {
              return [t.token_uid, []]
            }
          })
        )
        setEvidenceByToken(Object.fromEntries(pairs))
      } catch (e) {
        setError(e?.message || 'Failed to load supplier data')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const onUpload = async (e) => {
    e.preventDefault()
    setMessage('')
    setError('')

    if (!selectedTokenUid) {
      setError('Select a token')
      return
    }
    if (!file) {
      setError('Choose a file to upload')
      return
    }

    setUploading(true)
    try {
      await apiClient.uploadEvidenceForToken(selectedTokenUid, evidenceKind, file)
      setMessage('Uploaded successfully')
      setFile(null)

      const ev = await apiClient.fetchTokenEvidence(selectedTokenUid)
      setEvidenceByToken((prev) => ({ ...prev, [selectedTokenUid]: ev }))
    } catch (e2) {
      setError(e2?.message || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  if (loading) {
    return <div className="text-gray-600">Loading supplier portal…</div>
  }

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg shadow p-6">
        <h1 className="text-2xl font-bold text-gray-900">Supplier Portal</h1>
        <p className="text-gray-600 mt-1">Submit invoice/EPD evidence for your material tokens. Emissions totals are not shown in supplier mode.</p>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Upload Evidence</h2>
        {error ? <div className="mb-3 text-sm text-red-700">{error}</div> : null}
        {message ? <div className="mb-3 text-sm text-green-700">{message}</div> : null}

        <form className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end" onSubmit={onUpload}>
          <div>
            <label className="block text-sm font-medium text-gray-700">Token</label>
            <select
              className="mt-1 w-full border rounded px-3 py-2"
              value={selectedTokenUid}
              onChange={(ev) => setSelectedTokenUid(ev.target.value)}
            >
              {tokenOptions.map((uid) => (
                <option key={uid} value={uid}>{uid}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Evidence Type</label>
            <select
              className="mt-1 w-full border rounded px-3 py-2"
              value={evidenceKind}
              onChange={(ev) => setEvidenceKind(ev.target.value)}
            >
              <option value="invoice">Invoice</option>
              <option value="epd">EPD</option>
              <option value="other">Other</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">File</label>
            <input
              className="mt-1 w-full"
              type="file"
              onChange={(ev) => setFile(ev.target.files?.[0] || null)}
            />
            <button
              type="submit"
              disabled={uploading}
              className="mt-2 w-full px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded hover:bg-blue-700 disabled:opacity-50"
            >
              {uploading ? 'Uploading…' : 'Upload'}
            </button>
          </div>
        </form>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">My Tokens</h2>
        {tokens.length === 0 ? (
          <div className="text-gray-600">No tokens assigned to this supplier.</div>
        ) : (
          <div className="overflow-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-gray-600 border-b">
                  <th className="py-2 pr-4">Token</th>
                  <th className="py-2 pr-4">Material</th>
                  <th className="py-2 pr-4">Qty</th>
                  <th className="py-2 pr-4">Redeemed</th>
                  <th className="py-2 pr-4">Evidence Status</th>
                  <th className="py-2 pr-4">Notes</th>
                </tr>
              </thead>
              <tbody>
                {tokens.map((t) => {
                  const ev = evidenceByToken[t.token_uid] || []
                  const status = statusFromEvidence(ev)
                  const latest = ev?.[0]
                  return (
                    <tr key={t.token_uid} className="border-b last:border-b-0">
                      <td className="py-3 pr-4 font-mono text-xs text-gray-800">{t.token_uid}</td>
                      <td className="py-3 pr-4">{t.material_name}</td>
                      <td className="py-3 pr-4">{String(t.quantity)} {t.unit}</td>
                      <td className="py-3 pr-4">{t.redeemed ? 'Yes' : 'No'}</td>
                      <td className="py-3 pr-4">
                        <span className={`px-2 py-1 rounded ${status.tone}`}>{status.label}</span>
                      </td>
                      <td className="py-3 pr-4 text-gray-700">{latest?.verification_notes || ''}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
