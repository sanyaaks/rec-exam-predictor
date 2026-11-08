import { AlertTriangle, Brain, CheckCircle2, ChevronDown, Circle, Info, ListChecks, Trash2, Wand2, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ExamType, GeneratedQ, GenerateResult, RankerInfo, Readiness, TopicRow } from "../api";
import { EXAM_LABEL, PRIORITY_BAR } from "../lib/format";
import { Bar, Drawer, errMsg, PriorityPill, Spinner, useToast } from "./ui";

// ------------------------------------------------------------------ readiness checklist
const STATUS_ICON = {
  ok: <CheckCircle2 className="h-4 w-4 text-emerald-600" />,
  warn: <AlertTriangle className="h-4 w-4 text-amber-600" />,
  missing: <XCircle className="h-4 w-4 text-rose-600" />,
  info: <Info className="h-4 w-4 text-sky2-500" />,
};

function actionLink(sid: number, action: string | null): string | null {
  if (!action) return null;
  if (action === "upload") return `/app/upload?subject=${sid}`;
  return `/app/subjects/${sid}?tab=${action}`;
}

export function ReadinessPanel({ sid, exam }: { sid: number; exam: ExamType }) {
  const [data, setData] = useState<Readiness | null>(null);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    let alive = true;
    setData(null);
    api.readiness(sid, exam).then((r) => {
      if (!alive) return;
      setData(r);
      setOpen(r.checks.some((c) => c.status === "missing" || c.status === "warn"));
    }).catch(() => { /* non-blocking */ });
    return () => { alive = false; };
  }, [sid, exam]);
  if (!data) return null;
  const warn = data.checks.filter((c) => c.status === "warn").length;
  const missing = data.checks.filter((c) => c.status === "missing").length;
  return (
    <div className="card mb-5 overflow-hidden">
      <button className="flex w-full items-center gap-3 px-4 py-3 text-left" onClick={() => setOpen(!open)}>
        <ListChecks className="h-4 w-4 shrink-0 text-lav-500" />
        <div className="min-w-0 flex-1">
          <div className="text-sm font-semibold">Before you predict</div>
          <div className="text-xs muted">
            {data.summary}{warn ? ` · ${warn} thing${warn > 1 ? "s" : ""} worth checking` : ""}
          </div>
        </div>
        {missing > 0 && <span className="chip bg-rose-50 text-rose-700">{missing} missing</span>}
        <ChevronDown className={`h-4 w-4 shrink-0 transition ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <ul className="divide-y divide-line border-t border-line">
          {data.checks.map((c) => {
            const href = actionLink(sid, c.action);
            return (
              <li key={c.key} className="flex items-start gap-3 px-4 py-2.5 text-sm">
                <span className="mt-0.5 shrink-0">{STATUS_ICON[c.status]}</span>
                <div className="min-w-0 flex-1">
                  <div className="font-medium">{c.label}</div>
                  <div className="text-xs muted">{c.detail}</div>
                </div>
                {href && c.status !== "ok" && <Link to={href} className="shrink-0 text-xs text-lav-600 hover:underline">Fix →</Link>}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ ranker badge
export function RankerBadge({ r }: { r: RankerInfo }) {
  const ml = r.used === "ml";
  return (
    <div className={`flex items-start gap-2.5 rounded-xl border px-3.5 py-2.5 text-sm ${ml ? "border-lav-200 bg-lav-50 text-lav-800" : "border-line bg-white text-ink-soft"}`}>
      {ml ? <Brain className="mt-0.5 h-4 w-4 shrink-0" /> : <Circle className="mt-0.5 h-4 w-4 shrink-0 text-ink-mute" />}
      <div className="min-w-0">
        <b className="font-semibold">{ml ? `ML-assisted ranking (model v${r.model_version})` : "Statistical ranking"}</b>
        <span className="opacity-90"> — {r.reason}</span>
        {r.stale?.new_papers ? <div className="mt-0.5 text-xs text-amber-700">{r.stale.new_papers} paper(s) uploaded since this model was trained — retrain it in the Accuracy tab.</div> : null}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ unit override chips
export function UnitChips({ all, selected, configured, onChange }: { all: number[]; selected: number[]; configured: number[]; onChange: (u: number[] | null) => void }) {
  const isDefault = selected.length === configured.length && selected.every((u) => configured.includes(u));
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="mr-1 text-xs muted">Units in this exam:</span>
      {all.map((u) => {
        const on = selected.includes(u);
        return (
          <button key={u} onClick={() => {
            const next = on ? selected.filter((x) => x !== u) : [...selected, u].sort((a, b) => a - b);
            if (next.length) onChange(next);
          }} className={`chip transition ${on ? "bg-ink text-white" : "bg-white text-ink-soft ring-1 ring-line hover:bg-stone-50"}`}>Unit {u}</button>
        );
      })}
      {!isDefault && <button className="ml-1 text-xs text-lav-600 hover:underline" onClick={() => onChange(null)}>Reset to configured</button>}
    </div>
  );
}

// ------------------------------------------------------------------ topic ranking
function TopicItem({ t, onGenerate }: { t: TopicRow; onGenerate: () => void }) {
  const [open, setOpen] = useState(false);
  const st = t.stats;
  return (
    <li className="rounded-xl border border-line bg-white">
      <div className="flex items-center gap-3 px-3 py-2.5">
        <div className="w-6 shrink-0 text-right font-display text-sm font-semibold text-ink-mute">{t.rank}</div>
        <button className="min-w-0 flex-1 text-left" onClick={() => setOpen(!open)}>
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="truncate font-medium">{t.label}</span>
            {t.unit && <span className="chip bg-stone-100 text-ink-soft">Unit {t.unit}</span>}
            {t.pseudo && <span className="chip bg-amber-50 text-amber-700">Not in syllabus — review</span>}
          </div>
          <div className="mt-0.5 text-xs muted">
            {st.papers ? `Appeared in ${st.papers} of ${st.total_papers} papers` : "Not asked yet"}{st.last_year ? ` · last ${st.last_year}` : ""}
            {st.variants > 1 ? ` · ${st.variants} wordings` : ""}
          </div>
        </button>
        <div className="hidden shrink-0 sm:block"><PriorityPill p={t.priority} /></div>
        <div className="w-14 shrink-0 text-right">
          <div className="font-display text-base font-semibold">{Math.round(t.score)}</div>
          <Bar value={t.score} className={PRIORITY_BAR[t.priority]} />
        </div>
      </div>
      {open && (
        <div className="border-t border-line bg-[#fcfbf8] px-3 py-3 text-sm">
          <ul className="space-y-1 text-ink-soft">{t.reasons.map((r, i) => <li key={i} className="flex gap-2"><span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-lav-500" />{r}</li>)}</ul>
          {t.examples.length > 0 && <div className="mt-2 text-xs muted">e.g. “{t.examples[0]}”</div>}
          <div className="mt-2 text-[11px] muted">
            Statistical score {Math.round(t.stat_score)}{t.ml_rank_score !== undefined && t.ml_rank_score !== null ? ` · ML rank score ${Math.round(t.ml_rank_score)} (a rank percentile, not a probability)` : ""}
          </div>
          {!t.pseudo && <button className="btn-outline btn-sm mt-3" onClick={onGenerate}><Wand2 className="h-3.5 w-3.5" /> AI practice questions</button>}
          {t.pseudo && <p className="mt-2 text-xs text-amber-700">This concept isn't mapped to a syllabus topic. Map it in the subject's Review tab so it's counted with its topic.</p>}
        </div>
      )}
    </li>
  );
}

export function TopicRanking({ topics, onGenerate }: { topics: TopicRow[]; onGenerate: (t: TopicRow) => void }) {
  const [limit, setLimit] = useState(8);
  if (!topics.length) return null;
  return (
    <div className="card mb-5 p-4 sm:p-5">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="font-semibold">Topic ranking</h3>
        <span className="text-xs muted">Topics are ranked first; questions below inherit their topic's strength. Scores rank study priority — not probabilities.</span>
      </div>
      <ul className="space-y-1.5">{topics.slice(0, limit).map((t) => <TopicItem key={t.key} t={t} onGenerate={() => onGenerate(t)} />)}</ul>
      {topics.length > limit && <div className="mt-3 text-center"><button className="btn-ghost btn-sm" onClick={() => setLimit(limit + 12)}>Show more topics ({topics.length - limit} more)</button></div>}
    </div>
  );
}

// ------------------------------------------------------------------ grounded generation
export function GeneratedCard({ g, onDelete }: { g: GeneratedQ; onDelete?: () => void }) {
  const based = new Set(g.grounding?.based_on || []);
  const refs = (g.grounding?.retrieved || []).filter((r) => based.has(r.id));
  const ai = g.source === "llm";
  return (
    <div className={`rounded-xl border-2 border-dashed bg-white px-3 py-2.5 text-sm ${ai ? "border-lav-300" : "border-orange-200"}`}>
      <div className="mb-1 flex flex-wrap items-center gap-1.5">
        <span className={`chip ${ai ? "bg-lav-50 text-lav-700" : "bg-orange-50 text-orange-700"}`}><Wand2 className="h-3 w-3" /> {g.label}</span>
        <span className="chip bg-stone-100 text-ink-soft">{g.marks} marks</span>
        <span className="chip bg-stone-50 text-ink-mute">{g.kind === "variation" ? "Variation of a past question" : "New practice angle"}</span>
        {onDelete && <button className="btn-ghost btn-sm ml-auto" onClick={onDelete} aria-label="Delete"><Trash2 className="h-3.5 w-3.5" /></button>}
      </div>
      <p>{g.text}</p>
      {refs.length > 0 && (
        <div className="mt-1.5 text-xs muted">Based on: {refs.map((r) => `“${r.text}”${r.paper ? ` (${r.paper})` : ""}`).join("; ")}</div>
      )}
      <div className="mt-1 text-[11px] muted">Generated — never appeared in an exam.</div>
    </div>
  );
}

export function GeneratePanel({ sid, topic, exam, onClose }: { sid: number; topic: TopicRow | null; exam: ExamType; onClose: () => void }) {
  const { toast } = useToast();
  const [marks, setMarks] = useState(exam === "SEMESTER" ? 13 : 11);
  const [count, setCount] = useState(4);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<GenerateResult | null>(null);
  const [previous, setPrevious] = useState<GeneratedQ[]>([]);
  useEffect(() => {
    setResult(null);
    setMarks(exam === "SEMESTER" ? 13 : 11);
    if (topic) api.generated(sid, topic.topic).then(setPrevious).catch(() => setPrevious([]));
  }, [sid, topic, exam]);
  const run = async () => {
    if (!topic) return;
    setBusy(true);
    try {
      const r = await api.generateQuestions(sid, { topic: topic.topic, unit: topic.unit, marks, count });
      setResult(r);
      setPrevious((p) => [...r.questions, ...p.filter((x) => !r.questions.some((q) => q.id === x.id))]);
    } catch (e) { toast(errMsg(e), "error"); } finally { setBusy(false); }
  };
  const del = async (id: number) => {
    try { await api.deleteGenerated(id); setPrevious((p) => p.filter((x) => x.id !== id)); } catch (e) { toast(errMsg(e), "error"); }
  };
  const fresh = new Set(result?.questions.map((q) => q.id) || []);
  return (
    <Drawer open={!!topic} onClose={onClose} title={<span>AI practice questions <span className="font-normal muted">· {topic?.label}</span></span>}>
      {topic && (
        <div className="space-y-4">
          <p className="text-sm muted">
            Written from the syllabus topic and the most similar past questions from your uploads. They are practice material — clearly separate from real past questions.
          </p>
          <div className="card flex flex-wrap items-end gap-3 p-3">
            <label className="text-xs"><span className="label">Marks</span>
              <select className="input" value={marks} onChange={(e) => setMarks(Number(e.target.value))}>{[2, 11, 13, 15].map((m) => <option key={m} value={m}>{m} marks</option>)}</select>
            </label>
            <label className="text-xs"><span className="label">How many</span>
              <select className="input" value={count} onChange={(e) => setCount(Number(e.target.value))}>{[2, 3, 4, 6, 8].map((m) => <option key={m} value={m}>{m}</option>)}</select>
            </label>
            <button className="btn-primary" onClick={run} disabled={busy}>{busy ? <Spinner /> : <Wand2 className="h-4 w-4" />} Generate</button>
          </div>
          {result && (
            <div className="space-y-2">
              <p className="text-xs muted">{result.note}{result.discarded.length ? ` ${result.discarded.length} duplicate(s) of past questions were discarded.` : ""}</p>
              {result.retrieved.length > 0 && (
                <details className="rounded-xl bg-white px-3 py-2 text-xs ring-1 ring-line">
                  <summary className="cursor-pointer font-medium">Past questions used as reference ({result.retrieved.length})</summary>
                  <ul className="mt-1.5 space-y-1 muted">{result.retrieved.map((r) => <li key={r.id}>“{r.text}”{r.paper ? ` — ${r.paper}` : ""}</li>)}</ul>
                </details>
              )}
            </div>
          )}
          <div className="space-y-2">
            {previous.length === 0 && !busy && <p className="text-sm muted">Nothing generated for this topic yet.</p>}
            {previous.map((g) => (
              <div key={g.id} className={fresh.has(g.id) ? "" : "opacity-80"}><GeneratedCard g={g} onDelete={() => del(g.id)} /></div>
            ))}
          </div>
          <p className="text-[11px] muted">Exam: {EXAM_LABEL[exam]}</p>
        </div>
      )}
    </Drawer>
  );
}
