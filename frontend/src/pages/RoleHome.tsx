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
  fetchHealth,
  fetchProjects,
  fetchReports,
  downloadComplianceBundle,
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

  const [demoMode, setDemoMode] = useState(false);
  const [showHowItWorks, setShowHowItWorks] = useState(false);

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
    let cancelled = false;

    const checkHealth = async () => {
      try {
        const h = await fetchHealth();
        if (cancelled) return;
        setDemoMode(h.mode === 'demo');
      } catch {
        if (cancelled) return;
        setDemoMode(false);
      }
    };

    checkHealth();
    const interval = window.setInterval(checkHealth, 30000);

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

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [reportParams, role]);

  const onExportComplianceBundle = async (reportId: string) => {
    try {
      const blob = await downloadComplianceBundle(reportId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `mrv_compliance_bundle_${reportId}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.push('success', 'Compliance bundle downloaded.');
    } catch (err: unknown) {
      toast.push('error', getErrorMessage(err, 'Failed to export compliance bundle'));
    }
  };

  const lockingTooltip = 'LOCKED MRV reports are immutable (regulator-grade audit trail). Approved reports can be LOCKED by an admin to freeze calculations and evidence references.';
  const efTooltip = 'Emission factors are versioned and snapshotted in MRV reports. Once a report is approved/locked, its emission factor hash/value snapshot prevents recalculation drift.';
  const anomalyTooltip = 'Anomaly flags are automated alerts (e.g., unexpected values). They signal risk and require review, but do not change MRV totals by themselves.';

  const projectsTitle = role === 'contractor' ? 'My Projects' : 'Projects';
  const reportsTitle = role === 'mrv_officer' ? 'Pending Reviews' : role === 'admin' ? 'Pending Approvals' : 'My Reports';

  const canCreateReport = role === 'contractor' || role === 'project_manager';
  const hasPilotData = useMemo(
    () => projects.some((p) => Boolean(p.pilot)) || reports.some((r) => Boolean(r.pilot)) || adminApprovedReports.some((r) => Boolean(r.pilot)),
    [projects, reports, adminApprovedReports]
  );

  const demoBlockedMsg = 'This action is disabled in DEMO mode';

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
          <div className="flex items-center gap-2">
            {demoMode ? (
              <Badge title="Demo Mode">Demo Mode</Badge>
            ) : null}
            {hasPilotData ? (
              <Badge title="Pilot-tagged data (not a compliance claim)">Pilot Data</Badge>
            ) : null}
            <Badge title="This demo is for understanding workflow and auditability, not for making compliance claims.">Not a Compliance Claim</Badge>
          </div>
          <span className="text-xs text-slate-400">Backend: /api (Vite proxy)</span>
          <Link className="text-sm text-slate-200 hover:text-slate-50" to="/logout">Logout</Link>
        </div>
      </header>

      {demoMode ? (
        <div className="border-b border-slate-800 bg-slate-900/60 px-6 py-2 text-sm text-slate-100">
          <span className="font-semibold">DEMO MODE:</span> No real compliance claims. Writes may be restricted.
        </div>
      ) : null}

      <main className="flex-1 p-6">
        {loading && <p className="text-slate-300">Loading dashboard…</p>}
        {error && !loading && <p className="text-red-400 text-sm">Error: {error}</p>}

        {summary && !loading && (
          <>
            <div className="mb-2 flex items-center gap-2 text-sm text-slate-200">
              <span className="font-medium">KPIs</span>
              <button
                type="button"
                className="text-[11px] text-slate-500"
                title="What am I seeing? These KPIs are aggregated indicators computed from projects, MRV reports, evidence hashes, and anomalies. In Demo/Pilot mode, they are illustrative and not compliance claims."
                onClick={() => setShowHowItWorks(true)}
              >
                What am I seeing? (click)
              </button>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-6">
              <KpiCard label="Active Projects" value={summary.active_projects} />
              <KpiCard label="Total CO₂ Saved (tCO₂e)" tooltip={efTooltip} value={summary.total_co2_saved_t.toFixed(2)} />
              <KpiCard label="Open Anomalies" tooltip={anomalyTooltip} value={summary.open_anomalies} />
              <KpiCard label="Open Whistleblower Cases" value={summary.open_whistleblower_cases} />
            </div>

            <details className="mb-6 rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <summary className="cursor-pointer text-sm font-medium text-slate-100">
                How this is calculated
              </summary>
              <div className="mt-3 space-y-2 text-sm text-slate-300">
                <p>
                  <span className="font-medium text-slate-200">MRV locking:</span> <span title={lockingTooltip}>Approved reports can be locked to make them immutable.</span>
                </p>
                <p>
                  <span className="font-medium text-slate-200">Emission factor versioning:</span> <span title={efTooltip}>Reports snapshot the emission factor hash/value to prevent drift.</span>
                </p>
                <p>
                  <span className="font-medium text-slate-200">Anomaly flags:</span> <span title={anomalyTooltip}>Alerts highlight unusual patterns for review.</span>
                </p>
              </div>
            </details>

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
                          disabled={creating || demoMode}
                          className="rounded-lg bg-slate-50 text-slate-900 px-3 py-2 text-sm font-medium disabled:opacity-60"
                          title={demoMode ? demoBlockedMsg : undefined}
                        >
                          {creating ? 'Creating…' : demoMode ? 'Create report (disabled)' : 'Create report'}
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
                        <span className="text-slate-200 flex items-center gap-2">
                          <span>{p.name}</span>
                          {p.pilot ? <Badge title="Pilot-tagged data">Pilot Data</Badge> : null}
                        </span>
                        <span className="text-xs text-slate-500">{p.status}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </Panel>

              <Panel title={reportsTitle} titleTooltip={lockingTooltip}>
                {reports.length === 0 ? (
                  <p className="text-sm text-slate-400">No reports in this queue.</p>
                ) : (
                  <ul className="space-y-2">
                    {reports.slice(0, 10).map((r) => (
                      <li key={r.id} className="text-sm flex items-center justify-between gap-3">
                        <div className="flex flex-col">
                          <span className="text-slate-200 flex items-center gap-2">
                            <span>{r.reporting_period} · {r.status} · {r.total_co2e.toFixed(2)} tCO₂e</span>
                            {r.pilot ? <Badge title="Pilot-tagged data">Pilot Data</Badge> : null}
                          </span>
                          <span className="text-xs text-slate-500">{new Date(r.created_at).toLocaleString()}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          {(r.status === 'APPROVED' || r.status === 'LOCKED') ? (
                            <button
                              type="button"
                              onClick={() => onExportComplianceBundle(r.id)}
                              className="rounded-lg border border-slate-700 bg-slate-950/40 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-950"
                              title="Download the deterministic compliance ZIP bundle for this MRV report."
                            >
                              Export Compliance Bundle
                            </button>
                          ) : null}
                          {getPrimaryAction(r.status) ? (
                            <button
                              type="button"
                              disabled={advancingId === r.id || demoMode}
                              onClick={() => onAdvance(r.id, getPrimaryAction(r.status)!.next)}
                              className="rounded-lg bg-slate-50 text-slate-900 px-3 py-1.5 text-xs font-medium disabled:opacity-60"
                              title={demoMode ? demoBlockedMsg : (r.status === 'APPROVED' ? lockingTooltip : undefined)}
                            >
                              {advancingId === r.id ? 'Working…' : getPrimaryAction(r.status)!.label}
                            </button>
                          ) : null}
                        </div>
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
                            <span className="text-slate-200 flex items-center gap-2">
                              <span>{r.reporting_period} · {r.status} · {r.total_co2e.toFixed(2)} tCO₂e</span>
                              {r.pilot ? <Badge title="Pilot-tagged data">Pilot Data</Badge> : null}
                            </span>
                            <span className="text-xs text-slate-500">{new Date(r.created_at).toLocaleString()}</span>
                          </div>
                          <button
                            type="button"
                            disabled={advancingId === r.id || demoMode}
                            onClick={() => onAdvance(r.id, 'LOCKED')}
                            className="rounded-lg bg-slate-50 text-slate-900 px-3 py-1.5 text-xs font-medium disabled:opacity-60"
                            title={demoMode ? demoBlockedMsg : undefined}
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

      {showHowItWorks ? (
        <HowItWorksModal
          onClose={() => setShowHowItWorks(false)}
          demoMode={demoMode}
        />
      ) : null}
    </div>
  );
};

const Badge: React.FC<{ children: React.ReactNode; title?: string }> = ({ children, title }) => (
  <span
    className="rounded-md border border-slate-800 bg-slate-950/40 px-2 py-0.5 text-[11px] text-slate-200"
    title={title}
  >
    {children}
  </span>
);

const HowItWorksModal: React.FC<{ onClose: () => void; demoMode: boolean }> = ({ onClose, demoMode }) => (
  <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4">
    <div className="w-full max-w-2xl rounded-xl border border-slate-800 bg-slate-900 p-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold text-slate-50">How this works (read-only)</h2>
          <p className="mt-1 text-xs text-slate-400">
            A quick, non-technical explanation of what you’re seeing.
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg border border-slate-700 bg-slate-950/40 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-950"
        >
          Close
        </button>
      </div>

      <div className="mt-4 space-y-3 text-sm text-slate-200">
        <p>
          This dashboard shows an MRV (Measurement, Reporting, Verification) workflow for sustainable construction materials.
          It focuses on auditability: versioned emission factors, evidence hashes, and immutable lifecycle records.
        </p>
        <p>
          <span className="font-medium">KPIs</span> are aggregated indicators computed from the database (projects, MRV reports, anomalies).
        </p>
        <p>
          <span className="font-medium">Evidence</span> is stored with cryptographic hashes so reviewers can verify integrity.
        </p>
        <p>
          <span className="font-medium">Important:</span> {demoMode ? 'DEMO MODE is enabled.' : 'This environment may contain pilot-tagged data.'} This is not a compliance claim system.
        </p>
      </div>
    </div>
  </div>
);

const Panel: React.FC<{ title: string; titleTooltip?: string; children: React.ReactNode }> = ({ title, titleTooltip, children }) => (
  <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
    <div className="text-xs uppercase tracking-wide text-slate-400 mb-3 flex items-center gap-2">
      <span>{title}</span>
      {titleTooltip ? (
        <span
          className="text-[11px] text-slate-500"
          title={titleTooltip}
        >
          (?)
        </span>
      ) : null}
    </div>
    {children}
  </div>
);

const KpiCard: React.FC<{ label: string; tooltip?: string; value: string | number }> = ({ label, tooltip, value }) => (
  <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 flex flex-col gap-2">
    <span className="text-xs uppercase tracking-wide text-slate-400 flex items-center gap-2">
      <span>{label}</span>
      {tooltip ? (
        <span className="text-[11px] text-slate-500" title={tooltip}>
          (?)
        </span>
      ) : null}
    </span>
    <span className="text-2xl font-semibold">{value}</span>
  </div>
);
