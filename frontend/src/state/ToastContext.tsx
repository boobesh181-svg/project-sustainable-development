import React, { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react';

type ToastType = 'success' | 'error' | 'info';

type Toast = {
  id: string;
  type: ToastType;
  message: string;
};

type ToastApi = {
  push: (type: ToastType, message: string) => void;
};

const ToastContext = createContext<ToastApi | undefined>(undefined);

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timeouts = useRef(new Map<string, number>());

  const remove = useCallback((id: string) => {
    const handle = timeouts.current.get(id);
    if (handle) {
      window.clearTimeout(handle);
      timeouts.current.delete(id);
    }
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const push = useCallback(
    (type: ToastType, message: string) => {
      const id = `${Date.now()}_${Math.random().toString(16).slice(2)}`;
      setToasts((prev) => [{ id, type, message }, ...prev].slice(0, 3));
      const handle = window.setTimeout(() => remove(id), 4000);
      timeouts.current.set(id, handle);
    },
    [remove]
  );

  const value = useMemo(() => ({ push }), [push]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastViewport toasts={toasts} onDismiss={remove} />
    </ToastContext.Provider>
  );
};

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within ToastProvider');
  return ctx;
}

const ToastViewport: React.FC<{ toasts: Toast[]; onDismiss: (id: string) => void }> = ({ toasts, onDismiss }) => {
  if (toasts.length === 0) return null;

  return (
    <div className="fixed right-4 top-4 z-50 space-y-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={
            'w-[360px] max-w-[calc(100vw-2rem)] rounded-xl border px-4 py-3 shadow-sm ' +
            (t.type === 'success'
              ? 'border-emerald-800/50 bg-emerald-950/70 text-emerald-100'
              : t.type === 'error'
              ? 'border-red-800/50 bg-red-950/70 text-red-100'
              : 'border-slate-700 bg-slate-950/80 text-slate-100')
          }
        >
          <div className="flex items-start justify-between gap-3">
            <div className="text-sm">{t.message}</div>
            <button
              type="button"
              onClick={() => onDismiss(t.id)}
              className="text-xs text-slate-300 hover:text-slate-50"
              aria-label="Dismiss"
            >
              Dismiss
            </button>
          </div>
        </div>
      ))}
    </div>
  );
};
