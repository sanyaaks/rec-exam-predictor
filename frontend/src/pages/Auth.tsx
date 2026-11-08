import { FormEvent, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, auth } from "../api";
import { Logo } from "../components/Layout";
import { errMsg, Notice, Spinner } from "../components/ui";

const DEPARTMENTS = ["CSE", "IT", "AIDS", "AIML", "CSBS", "CSD", "ECE", "EEE", "MECH", "CIVIL", "AUTO", "BME", "BT", "CHEM", "MCT", "FT", "Other"];

export default function AuthPage({ mode }: { mode: "login" | "register" }) {
  const nav = useNavigate();
  const [params] = useSearchParams();
  const [form, setForm] = useState({ name: "", email: "", password: "", department: "CSE" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const next = params.get("next") || "/app";

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = mode === "login"
        ? await api.login({ email: form.email, password: form.password })
        : await api.register(form);
      auth.set(r.token, r.user);
      nav(next);
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  const guest = async () => {
    setBusy(true);
    try {
      const r = await api.guest();
      auth.set(r.token, r.user);
      nav("/app");
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      <div className="px-4 py-5 sm:px-6"><Logo /></div>
      <div className="flex flex-1 items-center justify-center px-4 pb-16">
        <div className="w-full max-w-sm">
          <h1 className="text-center text-2xl font-semibold">{mode === "login" ? "Welcome back" : "Create your account"}</h1>
          <p className="mt-1 text-center text-sm muted">
            {mode === "login" ? "Sign in to continue preparing." : "Your subjects, papers and predictions in one place."}
          </p>
          {params.get("expired") && <div className="mt-4"><Notice tone="warn">Your session expired. Please sign in again.</Notice></div>}
          <form onSubmit={submit} className="card mt-6 space-y-4 p-6">
            {mode === "register" && (
              <>
                <div>
                  <label className="label">Name</label>
                  <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Your name" />
                </div>
                <div>
                  <label className="label">Department</label>
                  <select className="input" value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })}>
                    {DEPARTMENTS.map((d) => <option key={d}>{d}</option>)}
                  </select>
                </div>
              </>
            )}
            <div>
              <label className="label">Email</label>
              <input className="input" type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="you@rajalakshmi.edu.in" autoComplete="email" />
            </div>
            <div>
              <label className="label">Password</label>
              <input className="input" type="password" required minLength={6} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} autoComplete={mode === "login" ? "current-password" : "new-password"} />
            </div>
            {error && <div className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>}
            <button className="btn-primary w-full py-2.5" disabled={busy}>{busy && <Spinner />}{mode === "login" ? "Sign in" : "Create account"}</button>
            {mode === "register" && <p className="text-xs muted">A sample Computer Networks subject (synthetic papers) is added so you can explore right away.</p>}
          </form>
          <div className="mt-5 text-center text-sm muted">
            {mode === "login" ? <>New here? <Link className="text-lav-600 hover:underline" to="/register">Create an account</Link></> : <>Already have an account? <Link className="text-lav-600 hover:underline" to="/login">Sign in</Link></>}
          </div>
          <div className="mt-2 text-center">
            <button className="text-sm text-ink-soft hover:text-ink hover:underline" onClick={guest} disabled={busy}>Just looking? Try the demo</button>
          </div>
        </div>
      </div>
    </div>
  );
}
