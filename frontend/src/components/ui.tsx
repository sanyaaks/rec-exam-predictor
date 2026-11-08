import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, CheckCircle2, Info, Loader2, X } from "lucide-react";
import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";
import type { Evidence, Priority } from "../api";
import { EVIDENCE_SHORT, EVIDENCE_STYLE, PRIORITY_LABEL, PRIORITY_STYLE } from "../lib/format";

export function Spinner({ className = "" }: { className?: string }) {
  return <Loader2 className={`h-4 w-4 animate-spin ${className}`} />;
}

export function PageLoader({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-24 text-sm muted">
      <Spinner /> {label}
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-xl bg-stone-200/60 ${className}`} />;
}

export function Empty({ icon, title, children, action }: { icon?: ReactNode; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-line bg-white/60 px-6 py-12 text-center">
      {icon && <div className="mb-3 rounded-2xl bg-lav-50 p-3 text-lav-600">{icon}</div>}
      <h3 className="text-base font-semibold">{title}</h3>
      {children && <div className="mt-1 max-w-md text-sm muted">{children}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function PriorityPill({ p }: { p: Priority }) {
  return <span className={`chip ${PRIORITY_STYLE[p]}`}>{PRIORITY_LABEL[p]}</span>;
}

export function EvidenceTag({ e }: { e: Evidence }) {
  return <span className={`chip ${EVIDENCE_STYLE[e]}`}>{EVIDENCE_SHORT[e]}</span>;
}

export function SampleBadge({ className = "" }: { className?: string }) {
  return (
    <span className={`chip bg-amber-50 text-amber-700 ring-1 ring-amber-200 ${className}`} title="These papers are synthetic, generated for the demo. They are not real REC / Anna University papers.">
      Sample data — synthetic papers
    </span>
  );
}

export function PageHeader({ title, subtitle, actions, eyebrow }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode; eyebrow?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        {eyebrow && <div className="mb-1 text-xs font-medium uppercase tracking-wide text-lav-600">{eyebrow}</div>}
        <h1 className="text-2xl font-semibold sm:text-[1.7rem]">{title}</h1>
        {subtitle && <p className="mt-1 text-sm muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function Modal({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: string; children: ReactNode; wide?: boolean }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    if (open) window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [open, onClose]);
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-50 flex items-end justify-center bg-ink/30 p-0 backdrop-blur-[2px] sm:items-center sm:p-4"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onMouseDown={onClose}>
          <motion.div onMouseDown={(e) => e.stopPropagation()}
            className={`card max-h-[92vh] w-full overflow-y-auto rounded-b-none p-5 sm:rounded-2xl ${wide ? "sm:max-w-2xl" : "sm:max-w-md"}`}
            initial={{ y: 16, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 16, opacity: 0 }}>
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-semibold">{title}</h3>
              <button className="btn-ghost btn-sm" onClick={onClose} aria-label="Close"><X className="h-4 w-4" /></button>
            </div>
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function Drawer({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    if (open) window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [open, onClose]);
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-50 flex justify-end bg-ink/25 backdrop-blur-[2px] no-print" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onMouseDown={onClose}>
          <motion.aside onMouseDown={(e) => e.stopPropagation()}
            className="flex h-full w-full max-w-xl flex-col bg-canvas shadow-lift"
            initial={{ x: 40, opacity: 0 }} animate={{ x: 0, opacity: 1 }} exit={{ x: 40, opacity: 0 }} transition={{ duration: 0.2 }}>
            <div className="flex items-start justify-between gap-3 border-b border-line bg-white px-5 py-4">
              <div className="min-w-0 text-base font-semibold">{title}</div>
              <button className="btn-ghost btn-sm" onClick={onClose} aria-label="Close"><X className="h-4 w-4" /></button>
            </div>
            <div className="flex-1 overflow-y-auto px-5 py-5">{children}</div>
          </motion.aside>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: { id: T; label: string; icon?: ReactNode }[]; value: T; onChange: (t: T) => void }) {
  return (
    <div className="-mx-4 mb-6 overflow-x-auto px-4 sm:mx-0 sm:px-0">
      <div className="inline-flex min-w-max gap-1 rounded-xl border border-line bg-white p-1 shadow-soft">
        {tabs.map((t) => (
          <button key={t.id} onClick={() => onChange(t.id)}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition ${value === t.id ? "bg-lav-100 font-medium text-lav-700" : "text-ink-soft hover:bg-stone-50"}`}>
            {t.icon}{t.label}
          </button>
        ))}
      </div>
    </div>
  );
}

export function Segmented<T extends string>({ options, value, onChange }: { options: { id: T; label: string }[]; value: T; onChange: (v: T) => void }) {
  return (
    <div className="inline-flex rounded-xl border border-line bg-white p-1">
      {options.map((o) => (
        <button key={o.id} onClick={() => onChange(o.id)}
          className={`rounded-lg px-3 py-1.5 text-sm transition ${value === o.id ? "bg-ink text-white" : "text-ink-soft hover:bg-stone-50"}`}>{o.label}</button>
      ))}
    </div>
  );
}

export function Stat({ label, value, hint, icon }: { label: string; value: ReactNode; hint?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between text-xs muted">{label}{icon}</div>
      <div className="mt-1 font-display text-2xl font-semibold">{value}</div>
      {hint && <div className="mt-0.5 text-xs muted">{hint}</div>}
    </div>
  );
}

export function Bar({ value, className = "bg-lav-500", track = "bg-stone-100" }: { value: number; className?: string; track?: string }) {
  return (
    <div className={`h-1.5 w-full overflow-hidden rounded-full ${track}`}>
      <div className={`h-full rounded-full ${className}`} style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
    </div>
  );
}

export function Notice({ tone = "info", children }: { tone?: "info" | "warn" | "ok"; children: ReactNode }) {
  const styles = {
    info: "bg-sky2-50 text-sky2-600 border-sky2-100",
    warn: "bg-amber-50 text-amber-800 border-amber-200",
    ok: "bg-emerald-50 text-emerald-800 border-emerald-200",
  }[tone];
  const Icon = tone === "warn" ? AlertTriangle : tone === "ok" ? CheckCircle2 : Info;
  return (
    <div className={`flex items-start gap-2.5 rounded-xl border px-3.5 py-2.5 text-sm ${styles}`}>
      <Icon className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="min-w-0">{children}</div>
    </div>
  );
}

// ------------------------------------------------------------------ toasts & confirm
type Toast = { id: number; msg: string; tone: "ok" | "error" | "info" };
const ToastCtx = createContext<{ toast: (msg: string, tone?: Toast["tone"]) => void; confirm: (msg: string, okLabel?: string) => Promise<boolean> }>({
  toast: () => {},
  confirm: async () => false,
});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [conf, setConf] = useState<{ msg: string; ok: string; resolve: (v: boolean) => void } | null>(null);
  const toast = useCallback((msg: string, tone: Toast["tone"] = "ok") => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, msg, tone }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4200);
  }, []);
  const confirm = useCallback((msg: string, ok = "Delete") => new Promise<boolean>((resolve) => setConf({ msg, ok, resolve })), []);
  const close = (v: boolean) => { conf?.resolve(v); setConf(null); };
  return (
    <ToastCtx.Provider value={{ toast, confirm }}>
      {children}
      <div className="pointer-events-none fixed bottom-4 left-1/2 z-[60] flex w-[min(92vw,420px)] -translate-x-1/2 flex-col gap-2 no-print">
        <AnimatePresence>
          {toasts.map((t) => (
            <motion.div key={t.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
              className={`pointer-events-auto rounded-xl px-4 py-2.5 text-sm shadow-lift ${t.tone === "error" ? "bg-rose-600 text-white" : t.tone === "info" ? "bg-white text-ink border border-line" : "bg-ink text-white"}`}>
              {t.msg}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
      <Modal open={!!conf} onClose={() => close(false)} title="Are you sure?">
        <p className="text-sm text-ink-soft">{conf?.msg}</p>
        <div className="mt-5 flex justify-end gap-2">
          <button className="btn-outline" onClick={() => close(false)}>Cancel</button>
          <button className="btn bg-rose-600 text-white hover:bg-rose-700" onClick={() => close(true)}>{conf?.ok}</button>
        </div>
      </Modal>
    </ToastCtx.Provider>
  );
}

export const useToast = () => useContext(ToastCtx);

export function errMsg(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}
