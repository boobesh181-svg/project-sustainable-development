export default function Sidebar({ currentPage, onPageChange }) {
  const pages = [
    { id: 'dashboard', label: 'Dashboard', icon: '📊' },
    { id: 'mrv', label: 'MRV Reports', icon: '📋' },
    { id: 'anomalies', label: 'Anomalies', icon: '⚠️' },
    { id: 'audit', label: 'Audit Trail', icon: '📜' },
  ]

  return (
    <aside className="w-64 bg-white shadow-lg">
      <div className="p-6">
        <h1 className="text-2xl font-bold text-blue-600">MRV System</h1>
        <p className="text-sm text-gray-600">Sustainable Construction</p>
      </div>

      <nav className="mt-8">
        {pages.map((page) => (
          <button
            key={page.id}
            onClick={() => onPageChange(page.id)}
            className={`w-full text-left px-6 py-3 flex items-center gap-3 transition-colors ${
              currentPage === page.id
                ? 'bg-blue-50 text-blue-600 border-l-4 border-blue-600'
                : 'text-gray-700 hover:bg-gray-50'
            }`}
          >
            <span className="text-xl">{page.icon}</span>
            <span className="font-medium">{page.label}</span>
          </button>
        ))}
      </nav>

      <div className="absolute bottom-0 left-0 right-0 p-6 border-t">
        <p className="text-xs text-gray-500 text-center">
          v1.0.0 | ISO-14064-2 Compliant
        </p>
      </div>
    </aside>
  )
}
