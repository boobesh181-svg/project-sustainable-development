export default function Loading() {
  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-50">
      <div className="text-center">
        <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-blue-100 mb-4">
          <div className="w-8 h-8 border-4 border-blue-300 border-t-blue-600 rounded-full animate-spin"></div>
        </div>
        <h2 className="text-lg font-semibold text-gray-900">Loading...</h2>
        <p className="text-sm text-gray-600 mt-2">Fetching data from backend</p>
      </div>
    </div>
  )
}
