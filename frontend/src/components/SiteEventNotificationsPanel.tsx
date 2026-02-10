import React, { useEffect, useMemo, useState } from 'react';

import {
  AcknowledgementStatusOut,
  NotificationOut,
  fetchAcknowledgementStatus,
  fetchPendingNotifications,
  respondToNotification,
} from '../services/api';
import { useToast } from '../state/ToastContext';

function formatDurationSeconds(seconds: number | null | undefined): string {
  const s = Math.max(0, Math.floor(seconds ?? 0));
  const hours = Math.floor(s / 3600);
  const mins = Math.floor((s % 3600) / 60);
  if (hours > 0) return `${hours}h ${mins}m`;
  return `${mins}m`;
}

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

export const SiteEventNotificationsPanel: React.FC = () => {
  const toast = useToast();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<NotificationOut[]>([]);

  const [selectedActivityId, setSelectedActivityId] = useState<string | null>(null);
  const [timeline, setTimeline] = useState<AcknowledgementStatusOut | null>(null);

  const pendingCount = pending.length;
  const demoFlag = useMemo(() => pending.some((n) => n.demo_watermark), [pending]);

  const refresh = async () => {
    setError(null);
    const data = await fetchPendingNotifications(50);
    setPending(data);
  };

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    refresh()
      .catch((e) => {
        if (!cancelled) setError(getErrorMessage(e, 'Failed to load notifications'));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    const interval = window.setInterval(() => {
      refresh().catch(() => undefined);
    }, 15000);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onRespond = async (notificationId: string, response_type: 'acknowledge' | 'comment' | 'dispute') => {
    try {
      const response_comment = response_type === 'comment' ? 'Noted.' : null;
      await respondToNotification(notificationId, { response_type, response_comment });
      toast.push('success', 'Response recorded (append-only).');
      await refresh();
    } catch (e: unknown) {
      toast.push('error', getErrorMessage(e, 'Failed to respond'));
    }
  };

  const onViewTimeline = async (activityId: string) => {
    try {
      setSelectedActivityId(activityId);
      setTimeline(null);
      const data = await fetchAcknowledgementStatus(activityId);
      setTimeline(data);
    } catch (e: unknown) {
      toast.push('error', getErrorMessage(e, 'Failed to load acknowledgement status'));
    }
  };

  return (
    <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold tracking-tight">Site Event Notifications</h2>
          <p className="text-xs text-slate-400">Contemporaneous acknowledgement requests (append-only records).</p>
        </div>
        <div className="text-right">
          <div className="text-xs text-slate-400">Pending</div>
          <div className="text-2xl font-semibold">{pendingCount}</div>
        </div>
      </div>

      {demoFlag ? (
        <div className="mt-3 rounded-lg border border-amber-900/40 bg-amber-950/30 px-3 py-2 text-xs text-amber-200">
          DEMO_ACKNOWLEDGEMENT: responses are watermarked in demo mode.
        </div>
      ) : null}

      {loading ? <p className="mt-3 text-sm text-slate-300">Loading…</p> : null}
      {error && !loading ? <p className="mt-3 text-sm text-red-400">Error: {error}</p> : null}

      {!loading && !error && pending.length === 0 ? (
        <p className="mt-3 text-sm text-slate-300">No pending notifications.</p>
      ) : null}

      <div className="mt-3 space-y-2">
        {pending.map((n) => (
          <div key={n.id} className="rounded-lg border border-slate-800 bg-slate-950/40 p-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="min-w-[240px]">
                <div className="text-xs text-slate-400">Activity</div>
                <div className="text-sm text-slate-100 break-all">{n.activity_id}</div>
              </div>
              <div className="min-w-[140px]">
                <div className="text-xs text-slate-400">Time remaining</div>
                <div className="text-sm text-slate-100">{formatDurationSeconds(n.seconds_remaining)}</div>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  className="rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-semibold hover:bg-emerald-500"
                  onClick={() => onRespond(n.id, 'acknowledge')}
                >
                  Acknowledge
                </button>
                <button
                  className="rounded-md bg-slate-800 px-3 py-1.5 text-xs font-semibold hover:bg-slate-700"
                  onClick={() => onRespond(n.id, 'comment')}
                >
                  Comment
                </button>
                <button
                  className="rounded-md bg-rose-700 px-3 py-1.5 text-xs font-semibold hover:bg-rose-600"
                  onClick={() => onRespond(n.id, 'dispute')}
                >
                  Dispute
                </button>
                <button
                  className="rounded-md border border-slate-700 bg-transparent px-3 py-1.5 text-xs font-semibold text-slate-200 hover:bg-slate-900"
                  onClick={() => onViewTimeline(n.activity_id)}
                >
                  Timeline
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {selectedActivityId ? (
        <div className="mt-4 rounded-lg border border-slate-800 bg-slate-950/40 p-3">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-slate-400">Acknowledgement status</div>
              <div className="text-sm text-slate-100 break-all">{selectedActivityId}</div>
            </div>
            <button
              className="rounded-md border border-slate-700 bg-transparent px-2 py-1 text-xs text-slate-200 hover:bg-slate-900"
              onClick={() => {
                setSelectedActivityId(null);
                setTimeline(null);
              }}
            >
              Close
            </button>
          </div>

          {timeline ? (
            <div className="mt-2 text-sm text-slate-200">
              <div className="text-xs text-slate-400">Derived</div>
              <div className="font-semibold">{timeline.derived_status}</div>
              <div className="mt-2 text-xs text-slate-400">Immutable timeline (notifications/responses)</div>
              <pre className="mt-1 max-h-48 overflow-auto rounded-md border border-slate-800 bg-slate-950 p-2 text-xs text-slate-200">
                {JSON.stringify(timeline, null, 2)}
              </pre>
            </div>
          ) : (
            <p className="mt-2 text-sm text-slate-300">Loading timeline…</p>
          )}
        </div>
      ) : null}
    </section>
  );
};
