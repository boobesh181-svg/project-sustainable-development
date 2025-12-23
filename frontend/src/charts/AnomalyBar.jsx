export default function AnomalyBar({ data }) {
  if (!data || data.length === 0) {
    return <div className="text-gray-500">No anomaly data available</div>
  }

  const maxCount = Math.max(...data.map(d => d.count || 0))
  const scale = maxCount > 0 ? 100 / maxCount : 1

  return (
    <div className="space-y-3">
      {data.map((point) => (
        <div key={point.date} className="space-y-1">
          <div className="flex justify-between items-center text-xs">
            <span className="font-medium text-gray-700">{point.date}</span>
            <span className="bg-red-100 text-red-700 px-2 py-1 rounded font-semibold">{point.count}</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
            <div
              className="bg-red-500 h-full transition-all duration-300"
              style={{ width: `${point.count * scale}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  )
}
