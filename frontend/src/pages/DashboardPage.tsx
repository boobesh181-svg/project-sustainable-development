import React, { useState } from "react";
import { DashboardSummary } from "../components/DashboardSummary";
import { Co2Trend } from "../components/Co2Trend";
import { Anomalies } from "../components/Anomalies";

export const DashboardPage: React.FC = () => {
  const [error, setError] = useState<string | null>(null);

  const handleError = (msg: string) => {
    setError(msg);
    setTimeout(() => setError(null), 5000);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-50">
      <header className="border-b border-slate-800 px-6 py-4">
        <h1 className="text-2xl font-semibold tracking-tight">
          Sustainable Construction MRV
        </h1>
        <p className="text-sm text-slate-400 mt-1">Dashboard</p>
      </header>

      <main className="p-6">
        {error && (
          <div className="mb-4 p-4 bg-red-900/20 border border-red-800 rounded-lg">
            <p className="text-red-200 text-sm">{error}</p>
          </div>
        )}

        <div className="space-y-6">
          {/* Summary KPIs */}
          <DashboardSummary onError={handleError} />

          {/* Charts Grid */}
          <div className="grid gap-6 lg:grid-cols-2">
            <div>
              <Co2Trend onError={handleError} />
            </div>
            <div>
              <Anomalies onError={handleError} />
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};
