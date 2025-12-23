export default function CO2Trend({ data }) {
  if (!data || data.length === 0) {
    return <div className="text-gray-500">No CO₂ data available</div>
  }

  const maxValue = Math.max(...data.map(d => Math.max(d.embodied || 0, d.operational || 0, d.saved || 0)))
  const scale = maxValue > 0 ? 100 / maxValue : 1

  return (
    <div className="space-y-4">
      {data.map((point) => (
        <div key={point.month} className="space-y-1">
          <div className="flex justify-between items-center text-xs">
            <span className="font-medium text-gray-700">{point.month}</span>
            <span className="text-gray-500">{(point.embodied + point.operational - point.saved).toFixed(1)}t</span>
          </div>
          <div className="flex gap-1 h-6 bg-gray-100 rounded overflow-hidden">
            {point.embodied > 0 && (
              <div
                className="bg-orange-500"
                style={{ width: `${(point.embodied * scale) / 3}%` }}
                title={`Embodied: ${point.embodied.toFixed(1)}t`}
              />
            )}
            {point.operational > 0 && (
              <div
                className="bg-red-500"
                style={{ width: `${(point.operational * scale) / 3}%` }}
                title={`Operational: ${point.operational.toFixed(1)}t`}
              />
            )}
            {point.saved > 0 && (
              <div
                className="bg-green-500"
                style={{ width: `${(point.saved * scale) / 3}%` }}
                title={`Saved: ${point.saved.toFixed(1)}t`}
              />
            )}
          </div>
        </div>
      ))}
      <div className="flex gap-4 mt-4 text-xs">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 bg-orange-500 rounded"></div>
          <span className="text-gray-600">Embodied</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 bg-red-500 rounded"></div>
          <span className="text-gray-600">Operational</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 bg-green-500 rounded"></div>
          <span className="text-gray-600">Saved</span>
        </div>
      </div>
    </div>
  )
}
