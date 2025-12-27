import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import {
  DashboardCharts,
  DashboardSummary,
  MRVReportSummary,
  Project,
  advanceReport,
  createReport,
  fetchDashboardCharts,
  fetchDashboardSummary,
  fetchProjects,
  fetchReports,
} from '../services/api';
import { useAuth } from '../state/AuthContext';
import { useToast } from '../state/ToastContext';

import { Co2TrendChart } from '../charts/Co2TrendChart';
import { MaterialMixChart } from '../charts/MaterialMixChart';
import { AnomalyTimelineChart } from '../charts/AnomalyTimelineChart';
import { DistanceHistogram } from '../charts/DistanceHistogram';
import { SupplierRiskScatter } from '../charts/SupplierRiskScatter';
import { Co2CostScatter } from '../charts/Co2CostScatter';

function getErrorMessage(error: unknown, fallback: string): string {
  if (typeof error === 'object' && error !== null) {
    const maybe = error as {
      response?: { data?: { detail?: unknown } };
      message?: unknown;
    };
    const detail = maybe.response?.data?.detail;
    if (typeof detail === 'string' && detail.trim()) return detail;
    if (typeof maybe.message === 'string' && maybe.message.trim()) return maybe.message;
  }
  return fallback;
}

export const RoleHome: React.FC = () => {
  const { user } = useAuth();
  const role = user?.role ?? '';
  const toast = useToast();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [charts, setCharts] = useState<DashboardCharts | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [reports, setReports] = useState<MRVReportSummary[]>([]);
  const [adminApprovedReports, setAdminApprovedReports] = useState<MRVReportSummary[]>([]);

  const [creating, setCreating] = useState(false);
  const [advancingId, setAdvancingId] = useState<string | null>(null);
  const [createForm, setCreateForm] = useState({
    project_id: '',
    reporting_period: '',
    sample_desc: '',
    parameter: '',
    value: '',
    total_co2e: '',
  });

  const reportParams = useMemo(() => {
    if (role === 'mrv_officer') return { status: 'SUBMITTED', limit: 50 };
    if (role === 'admin') return { status: 'VERIFIED', limit: 50 };
    return { limit: 50 };
  }, [role]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [s, c, p, r] = await Promise.all([
          fetchDashboardSummary(),
          fetchDashboardCharts(),
          fetchProjects(),
          fetchReports(reportParams),
        ]);
        setSummary(s);
        setCharts(c);
        setProjects(p);
        setReports(r);

        if (role === 'admin') {
          const approved = await fetchReports({ status: 'APPROVED', limit: 50 });
          setAdminApprovedReports(approved);
        } else {
          setAdminApprovedReports([]);
        }
      } catch (e: unknown) {
        setError(getErrorMessage(e, 'Failed to load dashboard'));
      } finally {
        setLoading(false);
      }
    })();
  }, [reportParams, role]);

  const projectsTitle = role === 'contractor' ? 'My Projects' : 'Projects';
  const reportsTitle = role === 'mrv_officer' ? 'Pending Reviews' : role === 'admin' ? 'Pending Approvals' : 'My Reports';

  const canCreateReport = role === 'contractor' || role === 'project_manager';

  const refreshReports = async () => {
    const [r, approved] = await Promise.all([
      fetchReports(reportParams),
      role === 'admin' ? fetchReports({ status: 'APPROVED', limit: 50 }) : Promise.resolve([] as MRVReportSummary[]),
    ]);
    setReports(r);
    setAdminApprovedReports(approved);
  };

  const onCreateReport = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    try {
      const total = Number(createForm.total_co2e);
      await createReport({
        project_id: createForm.project_id,
        reporting_period: createForm.reporting_period,
        sample_desc: createForm.sample_desc,
        parameter: createForm.parameter,
        value: createForm.value,
        total_co2e: total,
      });
      toast.push('success', 'MRV report created (DRAFT).');
      setCreateForm({ project_id: createForm.project_id, reporting_period: '', sample_desc: '', parameter: '', value: '', total_co2e: '' });
      await refreshReports();
    } catch (err: unknown) {
      toast.push('error', getErrorMessage(err, 'Failed to create report'));
    } finally {
      setCreating(false);
    }
  };

  const onAdvance = async (reportId: string, nextStatus: 'SUBMITTED' | 'VERIFIED' | 'APPROVED' | 'LOCKED') => {
    setAdvancingId(reportId);
    try {
      await advanceReport(reportId, nextStatus);
      toast.push('success', `Report advanced to ${nextStatus}.`);
      await refreshReports();
    } catch (err: unknown) {
      toast.push('error', getErrorMessage(err, 'Failed to advance report'));
    } finally {
      setAdvancingId(null);
    }
  };

  const getPrimaryAction = (status: string) => {
    if (status === 'DRAFT' && (role === 'contractor' || role === 'project_manager')) return { label: 'Submit', next: 'SUBMITTED' as const };
    if (status === 'SUBMITTED' && role === 'mrv_officer') return { label: 'Verify', next: 'VERIFIED' as const };
    if (status === 'VERIFIED' && role === 'admin') return { label: 'Approve', next: 'APPROVED' as const };
    if (status === 'APPROVED' && role === 'admin') return { label: 'Lock', next: 'LOCKED' as const };
    return null;
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-50">
      <header className="border-b border-slate-800 px-6 py-4 flex items-center justify-between">
        <div className="flex flex-col">
          <h1 className="text-lg font-semibold tracking-tight">MRV Dashboard</h1>
          <span className="text-xs text-slate-400">Signed in as {user?.email} ({role})</span>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-xs text-slate-400">Backend: /api (Vite proxy)</span>
          <Link className="text-sm text-slate-200 hover:text-slate-50" to="/logout">Logout</Link>
        </div>
      </header>

      <main className="flex-1 p-6">
        {loading && <p className="text-slate-300">Loading dashboard…</p>}
        {error && !loading && <p className="text-red-400 text-sm">Error: {error}</p>}

        {summary && !loading && (
          <>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-6">
              <KpiCard label="Active Projects" value={summary.active_projects} />
              <KpiCard label="Total CO₂ Saved (tCO₂e)" value={summary.total_co2_saved_t.toFixed(2)} />
              <KpiCard label="Open Anomalies" value={summary.open_anomalies} />
              <KpiCard label="Open Whistleblower Cases" value={summary.open_whistleblower_cases} />
            </div>

            {canCreateReport && (
              <div className="mb-6">
                <Panel title="Create MRV Report (DRAFT)">
                  {projects.length === 0 ? (
                    <p className="text-sm text-slate-400">No projects available to submit against.</p>
                  ) : (
                    <form onSubmit={onCreateReport} className="grid gap-3 lg:grid-cols-6">
                      <div className="lg:col-span-2">
                        <label className="block text-xs text-slate-400 mb-1">Project</label>
                        <select
                          className="w-full rounded-lg border border-slate-800 bg-slate-950/40 px-3 py-2 text-sm"
                          aria-label="Project"
                          value={createForm.project_id}
                          onChange={(e) => setCreateForm((p) => ({ ...p, project_id: e.target.value }))}
                          required
                        >
                          <option value="" disabled>Select a project</option>
                          {projects.map((p) => (
                            <option key={p.id} value={p.id}>{p.name}</option>
                          ))}
                        </select>
                      </div>

                      <div>
                        <label className="block text-xs text-slate-400 mb-1">Period</label>
                        <input
                          className="w-full rounded-lg border border-slate-800 bg-slate-950/40 px-3 py-2 text-sm"
                          value={createForm.reporting_period}
                          onChange={(e) => setCreateForm((p) => ({ ...p, reporting_period: e.target.value }))}
                          placeholder="2025-Q1"
                          required
                        />
                      </div>

                      <div>
                        <label className="block text-xs text-slate-400 mb-1">Total tCO₂e</label>
                        <input
                          className="w-full rounded-lg border border-slate-800 bg-slate-950/40 px-3 py-2 text-sm"
                          value={createForm.total_co2e}
                          onChange={(e) => setCreateForm((p) => ({ ...p, total_co2e: e.target.value }))}
                          inputMode="decimal"
                          placeholder="12.34"
                          required
                        />
                      </div>

                      <div className="lg:col-span-2">
                        <label className="block text-xs text-slate-400 mb-1">Sample Description</label>
                        <input
                          className="w-full rounded-lg border border-slate-800 bg-slate-950/40 px-3 py-2 text-sm"
                          value={createForm.sample_desc}
                          onChange={(e) => setCreateForm((p) => ({ ...p, sample_desc: e.target.value }))}
                          placeholder="e.g., Concrete batch A"
                          required
                        />
                      </div>

                      <div className="lg:col-span-3">
                        <label className="block text-xs text-slate-400 mb-1">Parameter</label>
                        <input
                          className="w-full rounded-lg border border-slate-800 bg-slate-950/40 px-3 py-2 text-sm"
                          value={createForm.parameter}
                          onChange={(e) => setCreateForm((p) => ({ ...p, parameter: e.target.value }))}
                          placeholder="e.g., Cement content"
                          required
                        />
                      </div>

                      <div className="lg:col-span-3">
                        <label className="block text-xs text-slate-400 mb-1">Value</label>
                        <input
                          className="w-full rounded-lg border border-slate-800 bg-slate-950/40 px-3 py-2 text-sm"
                          value={createForm.value}
                          onChange={(e) => setCreateForm((p) => ({ ...p, value: e.target.value }))}
                          placeholder="e.g., 320 kg/m³"
                          required
                        />
                      </div>

                      <div className="lg:col-span-6 flex justify-end">
                        <button
                          type="submit"
                          disabled={creating}
                          className="rounded-lg bg-slate-50 text-slate-900 px-3 py-2 text-sm font-medium disabled:opacity-60"
                        >
                          {creating ? 'Creating…' : 'Create report'}
                        </button>
                      </div>
                    </form>
                  )}
                </Panel>
              </div>
            )}

            <div className="grid gap-4 lg:grid-cols-2 mb-6">
              <Panel title={projectsTitle}>
                {projects.length === 0 ? (
                  <p className="text-sm text-slate-400">No projects visible.</p>
                ) : (
                  <ul className="space-y-2">
                    {projects.slice(0, 10).map((p) => (
                      <li key={p.id} className="text-sm flex items-center justify-between">
                        <span className="text-slate-200">{p.name}</span>
                        <span className="text-xs text-slate-500">{p.status}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </Panel>

              <Panel title={reportsTitle}>
                {reports.length === 0 ? (
                  <p className="text-sm text-slate-400">No reports in this queue.</p>
                ) : (
                  <ul className="space-y-2">
                    {reports.slice(0, 10).map((r) => (
                      <li key={r.id} className="text-sm flex items-center justify-between gap-3">
                        <div className="flex flex-col">
                          <span className="text-slate-200">{r.reporting_period} · {r.status} · {r.total_co2e.toFixed(2)} tCO₂e</span>
                          <span className="text-xs text-slate-500">{new Date(r.created_at).toLocaleString()}</span>
                        </div>
                        {getPrimaryAction(r.status) ? (
                          <button
                            type="button"
                            disabled={advancingId === r.id}
                            onClick={() => onAdvance(r.id, getPrimaryAction(r.status)!.next)}
                            className="rounded-lg bg-slate-50 text-slate-900 px-3 py-1.5 text-xs font-medium disabled:opacity-60"
                          >
                            {advancingId === r.id ? 'Working…' : getPrimaryAction(r.status)!.label}
                          </button>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                )}
              </Panel>
            </div>

            {role === 'admin' && (
              <div className="grid gap-4 lg:grid-cols-2 mb-6">
                <Panel title="Pending Lock">
                  {adminApprovedReports.length === 0 ? (
                    <p className="text-sm text-slate-400">No approved reports awaiting lock.</p>
                  ) : (
                    <ul className="space-y-2">
                      {adminApprovedReports.slice(0, 10).map((r) => (
                        <li key={r.id} className="text-sm flex items-center justify-between gap-3">
                          <div className="flex flex-col">
                            <span className="text-slate-200">{r.reporting_period} · {r.status} · {r.total_co2e.toFixed(2)} tCO₂e</span>
                            <span className="text-xs text-slate-500">{new Date(r.created_at).toLocaleString()}</span>
                          </div>
                          <button
                            type="button"
                            disabled={advancingId === r.id}
                            onClick={() => onAdvance(r.id, 'LOCKED')}
                            className="rounded-lg bg-slate-50 text-slate-900 px-3 py-1.5 text-xs font-medium disabled:opacity-60"
                          >
                            {advancingId === r.id ? 'Working…' : 'Lock'}
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </Panel>
                <div />
              </div>
            )}

            {charts && (
              <div className="space-y-6">
                <div className="grid gap-4 lg:grid-cols-3">
                  <div className="lg:col-span-2">
                    <Co2TrendChart data={charts.co2_trend} />
                  </div>
                  <div>
                    <MaterialMixChart data={charts.material_mix} />
                  </div>
                </div>

                <div className="grid gap-4 lg:grid-cols-2">
                  <AnomalyTimelineChart data={charts.anomaly_timeline} />
                  <DistanceHistogram data={charts.distance_histogram} />
                </div>

                <div className="grid gap-4 lg:grid-cols-2">
                  <SupplierRiskScatter data={charts.supplier_scatter} />
                  <Co2CostScatter data={charts.co2_cost_scatter} />
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
};

const Panel: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
    <div className="text-xs uppercase tracking-wide text-slate-400 mb-3">{title}</div>
    {children}
  </div>
);

const KpiCard: React.FC<{ label: string; value: string | number }> = ({ label, value }) => (
  <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 flex flex-col gap-2">
    <span className="text-xs uppercase tracking-wide text-slate-400">{label}</span>
    <span className="text-2xl font-semibold">{value}</span>
  </div>
);
