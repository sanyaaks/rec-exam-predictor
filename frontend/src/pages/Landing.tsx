import { motion } from "framer-motion";
import { ArrowRight, BarChart3, FileStack, FileText, ShieldCheck, Target, Upload } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, auth } from "../api";
import { Logo } from "../components/Layout";
import { errMsg, Spinner, useToast } from "../components/ui";

const FEATURES = [
  { icon: Upload, title: "Upload previous question papers", body: "Drop in CAT 1, CAT 2 and end-semester papers as PDF, Word or photos. Questions, marks and units are pulled out for you to review." },
  { icon: BarChart3, title: "Analyse examination trends", body: "See which units and topics keep coming back, how CAT and semester papers differ, and which parts of the syllabus have been skipped lately." },
  { icon: FileText, title: "Generate predicted question papers", body: "Get a full Part A / B / C paper that follows your exam pattern, with every question explained: how often it was asked, and why it's there." },
  { icon: Target, title: "Prepare strategically", body: "Open any question for an exam-style answer outline, save the ones that matter, and turn predictions into a day-by-day study plan." },
];

const STEPS = [
  ["Your papers, not guesses", "Every prediction is traced back to the papers you uploaded. Real past questions are shown with the year and paper they came from."],
  ["Reworded questions recognised", "Sentence-BERT (a small language model for meaning) and a classic TF-IDF word match work together, so \"Explain IPv6 architecture\" and \"Draw the IPv6 header\" count as the same concept."],
  ["Mapped to your syllabus", "Each question is placed under a syllabus unit and topic. Add your own keywords for tricky topics; anything unclear goes to a review list instead of being guessed."],
  ["Topics first, then questions", "Topics are ranked by how often and how recently they were asked, repetition cycles, unit rotation, usual marks and syllabus weight — separately for CAT 1, CAT 2 and semester exams."],
  ["ML only when it earns it", "An optional LightGBM model learns from your own history, but it is switched on only if it beats the simple statistical ranking on papers it never saw. With little data, statistics are used."],
  ["Checked against the past", "Each past paper is predicted using only the papers before it, and scored with Precision@K, Recall@K and NDCG@K. Scores rank what to study first — they are not probabilities or guarantees, and AI-generated practice questions are always labelled."],
];

export default function Landing() {
  const nav = useNavigate();
  const { toast } = useToast();
  const [busy, setBusy] = useState(false);
  const loggedIn = !!auth.token();

  const demo = async () => {
    setBusy(true);
    try {
      const r = await api.guest();
      auth.set(r.token, r.user);
      nav("/app");
    } catch (e) {
      toast(errMsg(e), "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen overflow-x-hidden bg-canvas">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-4 py-5 sm:px-6">
        <Logo />
        <div className="flex items-center gap-2">
          {loggedIn ? (
            <Link to="/app" className="btn-primary">Open dashboard</Link>
          ) : (
            <>
              <Link to="/login" className="btn-ghost">Sign in</Link>
              <Link to="/register" className="btn-primary hidden sm:inline-flex">Create account</Link>
            </>
          )}
        </div>
      </header>

      <section className="relative mx-auto max-w-6xl px-4 pb-16 pt-10 sm:px-6 sm:pt-16">
        <div className="pointer-events-none absolute -top-10 left-1/2 h-[420px] w-[min(900px,120vw)] -translate-x-1/2 rounded-full bg-gradient-to-br from-lav-200/60 via-sky2-100/50 to-transparent blur-3xl" />
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }} className="relative mx-auto max-w-3xl text-center">
          <span className="chip mb-5 bg-white text-ink-soft ring-1 ring-line">For Rajalakshmi Engineering College students</span>
          <h1 className="font-display text-4xl font-semibold leading-tight sm:text-6xl">
            Study Smarter.<br /><span className="bg-gradient-to-r from-lav-600 to-sky2-600 bg-clip-text text-transparent">Predict Better.</span>
          </h1>
          <p className="mx-auto mt-5 max-w-xl text-base text-ink-soft sm:text-lg">
            Your AI-powered examination companion, built around REC examination patterns.
          </p>
          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <button className="btn-primary px-6 py-3 text-base" onClick={() => nav(loggedIn ? "/app" : "/register")}>
              Start Predicting <ArrowRight className="h-4 w-4" />
            </button>
            <button className="btn-outline px-6 py-3 text-base" onClick={() => document.getElementById("features")?.scrollIntoView({ behavior: "smooth" })}>
              Explore Features
            </button>
          </div>
          <button onClick={demo} disabled={busy} className="mt-4 inline-flex items-center gap-2 text-sm text-lav-600 hover:underline">
            {busy && <Spinner />} or try the demo with sample papers — no sign-up
          </button>
        </motion.div>

        {/* product glimpse */}
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15, duration: 0.45 }}
          className="relative mx-auto mt-14 max-w-4xl">
          <div className="card overflow-hidden p-4 shadow-lift sm:p-6">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
              <div className="text-sm font-medium">Semester predictions · Computer Networks</div>
              <span className="chip bg-emerald-50 text-emerald-700">Based on 8 past papers</span>
            </div>
            {[
              { q: "Explain the architecture of IPv6 with a neat diagram.", m: 13, p: "Very high", tag: "Repeated concept", w: 86, c: "bg-lav-500" },
              { q: "Differentiate between TCP and UDP.", m: 2, p: "Very high", tag: "Exact repeat", w: 80, c: "bg-lav-500" },
              { q: "Explain link state routing with Dijkstra's algorithm.", m: 13, p: "High", tag: "Repeated concept", w: 68, c: "bg-sky2-500" },
            ].map((r) => (
              <div key={r.q} className="flex flex-col gap-2 border-t border-line py-3 first:border-t-0 sm:flex-row sm:items-center sm:gap-4">
                <div className="min-w-0 flex-1 text-sm">{r.q}</div>
                <div className="flex shrink-0 items-center gap-2 text-xs">
                  <span className="chip bg-stone-100 text-ink-soft">{r.m} marks</span>
                  <span className="chip bg-emerald-50 text-emerald-700">{r.tag}</span>
                  <div className="h-1.5 w-20 rounded-full bg-stone-100"><div className={`h-full rounded-full ${r.c}`} style={{ width: `${r.w}%` }} /></div>
                </div>
              </div>
            ))}
          </div>
        </motion.div>
      </section>

      <section id="features" className="mx-auto max-w-6xl scroll-mt-8 px-4 py-16 sm:px-6">
        <h2 className="text-center text-2xl font-semibold sm:text-3xl">Everything from past papers to exam day</h2>
        <div className="mt-10 grid gap-4 sm:grid-cols-2">
          {FEATURES.map(({ icon: Icon, title, body }, i) => (
            <motion.div key={title} initial={{ opacity: 0, y: 10 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.05 }}
              className="card p-6">
              <div className="mb-4 inline-flex rounded-xl bg-lav-50 p-2.5 text-lav-600"><Icon className="h-5 w-5" strokeWidth={1.8} /></div>
              <h3 className="text-lg font-semibold">{title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-ink-soft">{body}</p>
            </motion.div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
        <div className="rounded-3xl bg-gradient-to-br from-white to-lav-50 p-6 ring-1 ring-line sm:p-10">
          <div className="flex items-center gap-2 text-lav-600"><ShieldCheck className="h-5 w-5" /><span className="text-sm font-medium">How predictions work</span></div>
          <h2 className="mt-2 text-2xl font-semibold">Evidence you can check — never a promise</h2>
          <div className="mt-8 grid gap-6 sm:grid-cols-2">
            {STEPS.map(([t, b]) => (
              <div key={t}>
                <h3 className="font-semibold">{t}</h3>
                <p className="mt-1 text-sm leading-relaxed text-ink-soft">{b}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 pb-20 pt-4 text-center sm:px-6">
        <FileStack className="mx-auto h-8 w-8 text-lav-500" strokeWidth={1.5} />
        <h2 className="mt-3 text-2xl font-semibold">Ready for your next CAT?</h2>
        <div className="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
          <button className="btn-primary px-6 py-3" onClick={() => nav(loggedIn ? "/app" : "/register")}>Start Predicting</button>
          <button className="btn-outline px-6 py-3" onClick={demo} disabled={busy}>{busy && <Spinner />} Try the demo</button>
        </div>
        <p className="mx-auto mt-10 max-w-lg text-xs muted">
          An independent student tool. Not affiliated with or endorsed by Rajalakshmi Engineering College or Anna University. Predictions are not guaranteed.
        </p>
      </section>
    </div>
  );
}
