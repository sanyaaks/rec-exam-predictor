import { AnimatePresence, motion } from "framer-motion";
import { BookOpen, CalendarCheck, LayoutDashboard, LogOut, Menu, Sparkles, Upload, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { auth } from "../api";

const NAV = [
  { to: "/app", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/app/subjects", label: "Subjects", icon: BookOpen },
  { to: "/app/upload", label: "Upload papers", icon: Upload },
  { to: "/app/planner", label: "Study planner", icon: CalendarCheck },
];

export function Logo({ compact }: { compact?: boolean }) {
  return (
    <Link to="/" className="flex items-center gap-2">
      <span className="grid h-8 w-8 place-items-center rounded-xl bg-gradient-to-br from-lav-500 to-sky2-500 text-white shadow-soft">
        <Sparkles className="h-4 w-4" />
      </span>
      {!compact && (
        <span className="font-display text-[15px] font-semibold leading-tight">
          REC Exam <span className="text-lav-600">Predictor</span>
        </span>
      )}
    </Link>
  );
}

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="flex flex-col gap-1">
      {NAV.map(({ to, label, icon: Icon, end }) => (
        <NavLink key={to} to={to} end={end} onClick={onNavigate}
          className={({ isActive }) => `flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition ${isActive ? "bg-white font-medium text-ink shadow-soft" : "text-ink-soft hover:bg-white/70 hover:text-ink"}`}>
          <Icon className="h-4 w-4" strokeWidth={1.8} /> {label}
        </NavLink>
      ))}
    </nav>
  );
}

function UserBox() {
  const nav = useNavigate();
  const u = auth.user();
  return (
    <div className="rounded-2xl border border-line bg-white/70 p-3">
      <div className="flex items-center gap-2.5">
        <div className="grid h-8 w-8 place-items-center rounded-full bg-lav-100 text-sm font-semibold text-lav-700">
          {(u?.name || "?").slice(0, 1).toUpperCase()}
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-medium">{u?.name || "Student"}</div>
          <div className="truncate text-xs muted">{u?.is_guest ? "Guest session" : u?.email}</div>
        </div>
        <button className="btn-ghost btn-sm" title="Sign out" onClick={() => { auth.clear(); nav("/"); }}>
          <LogOut className="h-4 w-4" />
        </button>
      </div>
      {u?.is_guest && (
        <Link to="/register" className="mt-2 block text-xs text-lav-600 hover:underline">Create an account to keep your work →</Link>
      )}
    </div>
  );
}

export default function Layout() {
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  useEffect(() => setOpen(false), [loc.pathname]);
  return (
    <div className="min-h-screen bg-canvas">
      {/* desktop sidebar */}
      <aside className="no-print fixed inset-y-0 left-0 hidden w-60 flex-col gap-6 border-r border-line bg-[#f6f3ee] px-4 py-5 lg:flex">
        <Logo />
        <NavItems />
        <div className="mt-auto"><UserBox /></div>
      </aside>

      {/* mobile top bar */}
      <header className="no-print sticky top-0 z-40 flex items-center justify-between border-b border-line bg-canvas/90 px-4 py-3 backdrop-blur lg:hidden">
        <Logo />
        <button className="btn-ghost btn-sm" onClick={() => setOpen(true)} aria-label="Open menu"><Menu className="h-5 w-5" /></button>
      </header>
      <AnimatePresence>
        {open && (
          <motion.div className="fixed inset-0 z-50 bg-ink/25 lg:hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setOpen(false)}>
            <motion.div className="flex h-full w-72 flex-col gap-6 bg-[#f6f3ee] px-4 py-5" initial={{ x: -30 }} animate={{ x: 0 }} exit={{ x: -30 }} onClick={(e) => e.stopPropagation()}>
              <div className="flex items-center justify-between"><Logo /><button className="btn-ghost btn-sm" onClick={() => setOpen(false)}><X className="h-5 w-5" /></button></div>
              <NavItems onNavigate={() => setOpen(false)} />
              <div className="mt-auto"><UserBox /></div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <main className="min-w-0 overflow-x-clip px-4 py-6 sm:px-6 lg:ml-60 lg:px-10 lg:py-8">
        <motion.div key={loc.pathname} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }} className="mx-auto max-w-6xl">
          <Outlet />
        </motion.div>
      </main>
    </div>
  );
}
