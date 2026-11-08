import { Brain, Check, ChevronDown, Cpu, Gauge, Scale, X } from "lucide-react";
import { Fragment, useState } from "react";
import { api, ExamType, Fold, MatchLevel, ModelVersion, RankMetrics, RankerSummary, SubjectFull, WeightCompare } from "../../api";
import { Empty, errMsg, Notice, Segmented, Skeleton, Spinner, useToast } from "../../components/ui";
import { EXAM_LABEL, EXAM_TYPES, pct, relTime } from "../../lib/format";
import { useAsync, useMeta } from "../../lib/hooks";

export const MATCH_STYLE: Record<MatchLevel, string> = {
  exact: "bg-emerald-50 text-emerald-700",
  semantic: "bg-teal-50 text-teal-700",
  topic: "bg-sky2-50 text-sky2-600",
  miss: "bg-stone-100 text-stone-500",
};
export const MATCH_LABEL: Record<MatchLevel, string> = { exact: "Exact question", semantic: "Same concept", topic: "Same topic", miss: "Missed" };

type MetricKey = keyof RankMetrics;
const METRICS: { key: MetricKey; label: string; hint: string }[] = [
  { key: "precision@5", label: "Precision@5", hint: "Of the top 5 predicted topics, how many were actually asked." },
  { key: "precision@10", label: "Precision@10", hint: "Of the top 10 predicted topics, how many were actually asked." },
  { key: "recall@10", label: "Recall@10", hint: "Of all topics actually asked, how many were in the top 10." },
  { key: "ndcg@10", label: "NDCG@10", hint: "Ranking quality of the top 10 — topics asked more often count more, and being near the top counts more." },
  { key: "precision@R", label: "Precision@R", hint: "R = number of topics actually asked. Of the top R predicted topics, how many were asked." },
  { key: "ndcg@R", label: "NDCG@R", hint: "Ranking quality over the top R topics." },
  { key: "exact_match_rate", label: "Exact question match", hint: "Questions in the paper that matched a predicted question almost word-for-word." },
  { key: "semantic_topic_match_rate", label: "Semantic / topic match", hint: "Questions whose concept or syllabus topic was predicted (includes exact matches)." },
  { key: "unit_coverage", label: "Unit coverage", hint: "Share of the paper's units represented in the predicted questions." },
];
const RANKERS: { id: keyof RankerSummary; label: string }[] = [
  { id: "frequency_baseline", label: "Frequency only (baseline)" },
  { id: "statistical", label: "Statistical ranking" },
  { id: "ml", label: "ML-assisted" },
];

function MetricTable({ s }: { s: RankerSummary }) {
  const cols = RANKERS.filter((r) => s[r.id]);
  return (
    <div className="card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] text-sm">
          <thead><tr className="bg-stone-50 text-left text-xs muted">
            <th className="px-3 py-2 font-medium">Metric</th>
            {cols.map((c) => <th key={c.id} className="px-3 py-2 text-center font-medium">{c.label}<div className="font-normal">{s[c.id]?.folds} paper(s)</div></th>)}
          </tr></thead>
          <tbody>
            {METRICS.map((m) => {
              const vals = cols.map((c) => s[c.id]?.[m.key] as number | null | undefined);
              const best = Math.max(...vals.map((v) => (typeof v === "number" ? v : -1)));
              return (
                <tr key={m.key} className="border-t border-line">
                  <td className="px-3 py-2.5">
                    <div className="font-medium">{m.label}</div>
                    <div className="max-w-sm text-[11px] muted">{m.hint}</div>
                  </td>
                  {vals.map((v, i) => (
                    <td key={i} className={`px-3 py-2.5 text-center tabular-nums ${typeof v === "number" && v === best && best > 0 && cols.length > 1 ? "font-semibold text-lav-700" : ""}`}>
                      {m.key.startsWith("ndcg") ? (typeof v === "number" ? v.toFixed(2) : "—") : pct(v)}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function FoldRow({ f }: { f: Fold }) {
  const [open, setOpen] = useState(false);
  const best = f.ml || f.statistical;
  return (
    <Fragment>
      <tr className="cursor-pointer border-t border-line hover:bg-stone-50" onClick={() => setOpen(!open)}>
        <td className="px-3 py-2.5"><div className="flex items-center gap-1.5"><ChevronDown className={`h-3.5 w-3.5 shrink-0 transition ${open ? "rotate-180" : ""}`} />{f.paper}</div></td>
        <td className="px-3 py-2.5 text-center muted">{f.train_papers}</td>
        <td className="px-3 py-2.5 text-center muted">{f.relevant_topics}{f.novel_topics ? <span className="text-[11px]"> ({f.novel_topics} new)</span> : null}</td>
        <td className="px-3 py-2.5 text-center">{pct(f.statistical["precision@R"])} <span className="text-xs muted">/ {pct(f.frequency_baseline["precision@R"])}</span></td>
        <td className="px-3 py-2.5 text-center">{f.statistical["ndcg@R"].toFixed(2)}{f.ml ? <span className="text-xs text-lav-700"> · ML {f.ml["ndcg@R"].toFixed(2)}</span> : null}</td>
        <td className="px-3 py-2.5 text-center">{pct(best.exact_match_rate)}</td>
        <td className="px-3 py-2.5 text-center font-medium">{pct(best.semantic_topic_match_rate)}</td>
      </tr>
      {open && (
        <tr><td colSpan={7} className="bg-subtle px-3 py-3">
          <div className="grid gap-4 lg:grid-cols-2">
            <div>
              <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wide muted">Top predicted topics</h4>
              <ul className="space-y-1">
                {(f.top_topics || []).map((t, i) => (
                  <li key={i} className="flex items-center gap-2 text-sm">
                    {t.asked ? <Check className="h-3.5 w-3.5 shrink-0 text-emerald-600" /> : <X className="h-3.5 w-3.5 shrink-0 text-stone-400" />}
                    <span className="min-w-0 truncate">{i + 1}. {t.label}</span>
                    <span className="ml-auto shrink-0 text-xs muted">{t.unit ? `U${t.unit} · ` : ""}{Math.round(t.score)}</span>
                  </li>
                ))}
              </ul>
              {!!f.missed_topics?.length && (
                <p className="mt-2 text-xs muted">Asked but not in the top {f.relevant_topics}: {f.missed_topics.join(", ")}</p>
              )}
            </div>
            <div>
              <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wide muted">Each question in the paper</h4>
              <ul className="space-y-1.5">
                {(f.rows || []).map((r, i) => (
                  <li key={i} className="rounded-lg bg-white px-3 py-2 text-sm ring-1 ring-line">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={`chip ${MATCH_STYLE[r.match]}`}>{MATCH_LABEL[r.match]}</span>
                      <span className="text-xs muted">{r.marks ? `${r.marks} marks` : ""}{r.unit ? ` · Unit ${r.unit}` : ""}{r.topic ? ` · ${r.topic}` : ""}</span>
                    </div>
                    <div className="mt-1">{r.text}</div>
                    {r.predicted && <div className="mt-1 text-xs muted">Predicted: “{r.predicted}”</div>}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </td></tr>
      )}
    </Fragment>
  );
}

function CompareWeights({ subject, onApplied }: { subject: SubjectFull; onApplied: () => void }) {
  const { toast } = useToast();
  const [exam, setExam] = useState<ExamType>("SEMESTER");
  const [data, setData] = useState<WeightCompare | null>(null);
  const [busy, setBusy] = useState(false);
  const [applying, setApplying] = useState<string | null>(null);

  const run = async (et = exam) => {
    setBusy(true);
    try { setData(await api.compareWeights(subject.id, et)); } catch (e) { toast(errMsg(e), "error"); } finally { setBusy(false); }
  };
  const apply = async (name: string, weights: Record<string, number>) => {
    setApplying(name);
    try {
      await api.patchSubject(subject.id, { weights: { ...subject.weights_by_type, [exam]: weights } });
      toast(`Applied “${name}” weights to ${EXAM_LABEL[exam]}`);
      onApplied();
    } catch (e) { toast(errMsg(e), "error"); } finally { setApplying(null); }
  };

  const labels = Object.keys(subject.weights);
  return (
    <div className="card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="flex items-center gap-2 font-semibold"><Scale className="h-4 w-4 text-lav-500" /> Compare weightings</h3>
          <p className="mt-0.5 max-w-xl text-sm muted">Re-runs the backtest with several weight presets to see which would have ranked your past {EXAM_LABEL[exam]} papers best. Weights are saved separately for each exam type.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Segmented<ExamType> value={exam} onChange={(v) => { setExam(v); setData(null); }} options={EXAM_TYPES.map((t) => ({ id: t, label: EXAM_LABEL[t] }))} />
          <button className="btn-outline" onClick={() => run()} disabled={busy}>{busy ? <Spinner /> : <Scale className="h-4 w-4" />} {data ? "Run again" : "Run comparison"}</button>
        </div>
      </div>
      {busy && !data && <p className="mt-3 text-xs muted">This takes a few seconds…</p>}
      {data && (
        <div className="mt-4">
          {!data.enough_data && data.rows.length > 0 && <div className="mb-3"><Notice tone="warn">Only {data.folds} {EXAM_LABEL[exam]} paper(s) could be tested — treat differences as a rough hint.</Notice></div>}
          {data.rows.length === 0 ? <p className="text-sm muted">{data.note}</p> : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-sm">
                <thead><tr className="text-left text-xs muted">
                  <th className="px-3 py-2 font-medium">Weighting</th>
                  <th className="px-3 py-2 text-center font-medium">Overall</th>
                  <th className="px-3 py-2 text-center font-medium">P@5</th>
                  <th className="px-3 py-2 text-center font-medium">R@10</th>
                  <th className="px-3 py-2 text-center font-medium">NDCG@R</th>
                  <th className="px-3 py-2 text-center font-medium">Exact</th>
                  <th className="px-3 py-2 text-center font-medium">Topic match</th>
                  <th className="px-3 py-2" />
                </tr></thead>
                <tbody>
                  {data.rows.map((r) => {
                    const best = r.name === data.best;
                    const current = r.name === "Your current weights";
                    return (
                      <tr key={r.name} className={`border-t border-line ${best ? "bg-lav-50/70" : ""}`}>
                        <td className="px-3 py-2.5">
                          <div className="flex flex-wrap items-center gap-1.5 font-medium">
                            {r.name}
                            {current && <span className="chip bg-stone-100 text-ink-soft">in use</span>}
                            {best && <span className="chip bg-lav-500 text-white">Best</span>}
                          </div>
                          <div className="mt-0.5 text-[11px] muted">{labels.map((k) => `${k.replace(/_/g, " ")} ${Math.round((r.weights[k] || 0) * 100)}%`).join(" · ")}</div>
                        </td>
                        <td className="px-3 py-2.5 text-center font-semibold">{Math.round(r.objective * 100)}</td>
                        <td className="px-3 py-2.5 text-center">{pct(r["precision@5"])}</td>
                        <td className="px-3 py-2.5 text-center">{pct(r["recall@10"])}</td>
                        <td className="px-3 py-2.5 text-center">{r["ndcg@R"].toFixed(2)}</td>
                        <td className="px-3 py-2.5 text-center">{pct(r.exact_match_rate)}</td>
                        <td className="px-3 py-2.5 text-center">{pct(r.semantic_topic_match_rate)}</td>
                        <td className="px-3 py-2.5 text-right">
                          {!current && <button className="btn-outline btn-sm" disabled={!!applying} onClick={() => apply(r.name, r.weights)}>{applying === r.name && <Spinner />} Apply to {EXAM_LABEL[exam]}</button>}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          <p className="mt-3 text-xs muted">{data.note}</p>
        </div>
      )}
    </div>
  );
}

const STATUS_CHIP: Record<string, string> = {
  active: "bg-emerald-50 text-emerald-700", rejected: "bg-stone-100 text-stone-500",
  archived: "bg-slate-100 text-slate-500", candidate: "bg-sky2-50 text-sky2-600",
};

function ModelRow({ m, onChange }: { m: ModelVersion; onChange: () => void }) {
  const { toast } = useToast();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const act = async (fn: () => Promise<unknown>, msg: string) => {
    setBusy(true);
    try { await fn(); toast(msg); onChange(); } catch (e) { toast(errMsg(e), "error"); } finally { setBusy(false); }
  };
  const g = m.gate;
  return (
    <div className="rounded-xl border border-line bg-white">
      <div className="flex flex-wrap items-center gap-2 px-3 py-2.5 text-sm">
        <button className="flex min-w-0 flex-1 items-center gap-2 text-left" onClick={() => setOpen(!open)}>
          <ChevronDown className={`h-3.5 w-3.5 shrink-0 transition ${open ? "rotate-180" : ""}`} />
          <span className="font-medium">Version {m.version}</span>
          <span className={`chip ${STATUS_CHIP[m.status] || ""}`}>{m.status}</span>
          <span className="truncate text-xs muted">{m.kind} · {m.train_papers} papers · {relTime(m.created_at)}</span>
        </button>
        {m.status !== "active" && g.use_ml && <button className="btn-outline btn-sm" disabled={busy} onClick={() => act(() => api.activateModel(m.id), `Model v${m.version} activated`)}>Activate</button>}
        {m.status === "active" && <button className="btn-ghost btn-sm" disabled={busy} onClick={() => act(() => api.archiveModel(m.id), `Model v${m.version} archived — statistical ranking will be used`)}>Archive</button>}
      </div>
      {open && (
        <div className="border-t border-line bg-subtle px-3 py-3 text-sm">
          <p className="text-ink-soft">{g.reason}</p>
          <p className="mt-1 text-xs muted">
            {g.dated_papers ?? "?"} dated papers · {g.origins ?? "?"} evaluation points · {g.positives ?? "?"} topic appearances
            {g.gate ? ` (needs ${g.gate.min_dated_papers} / ${g.gate.min_origins} / ${g.gate.min_positives})` : ""}
          </p>
          {!!g.validation?.length && (
            <table className="mt-2 w-full max-w-md text-xs">
              <thead><tr className="text-left muted"><th className="py-1 font-medium">Held-out paper</th><th className="py-1 text-center font-medium">Statistical NDCG</th><th className="py-1 text-center font-medium">ML NDCG</th></tr></thead>
              <tbody>{g.validation.map((v) => (
                <tr key={v.paper} className="border-t border-line">
                  <td className="py-1">{v.paper}</td>
                  <td className="py-1 text-center">{v.statistical_ndcg.toFixed(2)}</td>
                  <td className={`py-1 text-center ${v.ml_ndcg > v.statistical_ndcg ? "font-semibold text-emerald-700" : ""}`}>{v.ml_ndcg.toFixed(2)}</td>
                </tr>
              ))}</tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}

function ModelsSection({ subject, onChange }: { subject: SubjectFull; onChange: () => void }) {
  const { toast } = useToast();
  const { data, reload } = useAsync(() => api.models(subject.id), [subject.id]);
  const [training, setTraining] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const train = async () => {
    setTraining(true);
    try { const r = await api.trainModel(subject.id); setMessage(r.message); reload(true); onChange(); }
    catch (e) { toast(errMsg(e), "error"); } finally { setTraining(false); }
  };
  return (
    <div className="card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="flex items-center gap-2 font-semibold"><Brain className="h-4 w-4 text-lav-500" /> Prediction models</h3>
          <p className="mt-0.5 max-w-2xl text-sm muted">
            An optional LightGBM model learns which topic signals mattered in your past papers. With little data we use statistical ranking instead of forcing ML — a model is only switched on if it beats statistical ranking on papers it never saw.
          </p>
        </div>
        <button className="btn-outline" onClick={train} disabled={training || data?.ml_backend === null}>{training ? <Spinner /> : <Cpu className="h-4 w-4" />} {data?.models.length ? "Retrain model" : "Train model"}</button>
      </div>
      {data?.ml_backend === null && <div className="mt-3"><Notice tone="info">No ML library is installed on the server, so statistical ranking is always used.</Notice></div>}
      {message && <div className="mt-3"><Notice tone={message.toLowerCase().includes("beat statistical") && !message.toLowerCase().includes("did not") ? "ok" : "info"}>{message}</Notice></div>}
      {data && (
        <div className="mt-4 space-y-2">
          <div className="text-xs muted">
            {data.active ? <>Active: <b className="text-ink">version {data.active.version}</b> ({data.active.kind}).</> : "No active model — predictions use statistical ranking."}
            {data.active && !!data.staleness.new_papers && <span className="text-amber-700"> {data.staleness.new_papers} paper(s) added since training — retrain to include them.</span>}
          </div>
          {data.models.length === 0 ? <p className="text-sm muted">No model trained yet.</p> : data.models.map((m) => <ModelRow key={m.id} m={m} onChange={() => { reload(true); onChange(); }} />)}
        </div>
      )}
    </div>
  );
}

export function EngineLine() {
  const meta = useMeta();
  const e = meta?.engine;
  if (!e) return null;
  return (
    <p className="text-[11px] muted">
      Engine v{e.version} · similarity: {e.similarity} · ML library: {e.ml_backend || "none"}
    </p>
  );
}

export default function AccuracyTab({ subject, onApplied }: { subject: SubjectFull; onApplied: () => void }) {
  const { data, loading, error, reload } = useAsync(() => api.backtest(subject.id), [subject.id, JSON.stringify(subject.weights_by_type)]);
  const [view, setView] = useState<"ALL" | ExamType>("ALL");
  if (error) return <Notice tone="warn">{error}</Notice>;
  if (loading && !data) return <div className="space-y-3"><Skeleton className="h-24" /><Skeleton className="h-72" /></div>;
  if (!data) return null;
  const summary = view === "ALL" ? data.summary : data.by_exam_type[view];
  const folds = view === "ALL" ? data.folds : data.folds.filter((f) => f.exam_type === view);

  return (
    <div className="space-y-5">
      <div className="card p-5">
        <h3 className="flex items-center gap-2 font-semibold"><Gauge className="h-4 w-4 text-lav-500" /> How well would this have worked before?</h3>
        <p className="mt-1 max-w-3xl text-sm muted">{data.note}</p>
        <div className="mt-2"><EngineLine /></div>
      </div>
      {!!data.undated_papers?.length && <Notice tone="warn">{data.undated_papers.length} paper(s) have no exam year and are left out: {data.undated_papers.join(", ")}. Add the year in Documents.</Notice>}

      {!data.folds.length ? (
        <Empty title="Not enough history to test yet">
          Each tested paper needs at least two earlier dated papers. Upload more past papers (with exam years) to see how accurate predictions have been.
        </Empty>
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <Segmented<"ALL" | ExamType> value={view} onChange={setView}
              options={[{ id: "ALL", label: "All" }, ...EXAM_TYPES.filter((t) => data.by_exam_type[t]).map((t) => ({ id: t, label: EXAM_LABEL[t] }))]} />
            {!data.enough_data && <span className="text-xs text-amber-700">Only {data.folds.length} paper tested — rough indication only.</span>}
          </div>
          {summary ? <MetricTable s={summary} /> : <p className="text-sm muted">No tested papers for this exam type.</p>}
          {!summary?.ml && data.ml_backend && <p className="text-xs muted">ML-assisted column appears once at least 3 earlier papers can be used to train it at each test point.</p>}

          <div className="card overflow-hidden">
            <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
              <h3 className="font-semibold">Each tested paper</h3>
              <span className="text-xs muted">Click a row for topic hits and every question</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-sm">
                <thead><tr className="bg-stone-50 text-left text-xs muted">
                  <th className="px-3 py-2 font-medium">Paper (hidden)</th>
                  <th className="px-3 py-2 text-center font-medium">Earlier papers</th>
                  <th className="px-3 py-2 text-center font-medium">Topics asked (R)</th>
                  <th className="px-3 py-2 text-center font-medium">P@R / baseline</th>
                  <th className="px-3 py-2 text-center font-medium">NDCG@R</th>
                  <th className="px-3 py-2 text-center font-medium">Exact</th>
                  <th className="px-3 py-2 text-center font-medium">Topic match</th>
                </tr></thead>
                <tbody>{folds.map((f) => <FoldRow key={f.paper_id} f={f} />)}</tbody>
              </table>
            </div>
          </div>
        </>
      )}

      <ModelsSection subject={subject} onChange={() => reload(true)} />
      <CompareWeights subject={subject} onApplied={() => { onApplied(); reload(); }} />
    </div>
  );
}
