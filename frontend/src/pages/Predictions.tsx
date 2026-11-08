import { Download, FileDown, Info, Search, Sparkles } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, downloadFile, Evidence, ExamType, PredItem, Priority, TopicRow } from "../api";
import { GeneratePanel, RankerBadge, ReadinessPanel, TopicRanking, UnitChips } from "../components/EngineWidgets";
import PredictionCard from "../components/PredictionCard";
import PreparePanel, { useSaveQuestion } from "../components/PreparePanel";
import { Empty, errMsg, Notice, PageHeader, Segmented, Skeleton, Spinner, useToast } from "../components/ui";
import { EVIDENCE_SHORT, EXAM_LABEL, PRIORITY_HEX, PRIORITY_LABEL, QTYPE_LABEL } from "../lib/format";
import { useAsync } from "../lib/hooks";

const PRIORITIES: Priority[] = ["very_high", "high", "moderate", "lower"];

export default function PredictionsPage() {
  const sid = Number(useParams().id);
  const [params, setParams] = useSearchParams();
  const exam = ((params.get("exam") as ExamType) || "SEMESTER");
  const nav = useNavigate();
  const { toast } = useToast();
  const save = useSaveQuestion(sid);
  const { data: subject } = useAsync(() => api.subject(sid), [sid]);
  const [unitOverride, setUnitOverride] = useState<number[] | null>(null);
  const { data, loading, error } = useAsync(() => api.predictions(sid, exam, unitOverride), [sid, exam, (unitOverride || []).join(",")]);
  const [genTopic, setGenTopic] = useState<TopicRow | null>(null);
  const unitsQ = unitOverride && unitOverride.length ? `&units=${unitOverride.join(",")}` : "";
  const allUnits = useMemo(() => {
    const n = subject?.units.length ? subject.units.map((u) => u.number) : Array.from({ length: subject?.exam_config.units_count || 5 }, (_, i) => i + 1);
    return n.sort((a, b) => a - b);
  }, [subject]);
  const [f, setF] = useState({ marks: "", unit: "", priority: "", qtype: "", evidence: "", q: "" });
  const [limit, setLimit] = useState(30);
  const [preparing, setPreparing] = useState<PredItem | null>(null);
  const [generating, setGenerating] = useState(false);

  const items = useMemo(() => {
    if (!data) return [];
    const q = f.q.trim().toLowerCase();
    return data.items.filter((it) =>
      (!f.marks || String(it.marks) === f.marks) &&
      (!f.unit || String(it.unit) === f.unit) &&
      (!f.priority || it.priority === f.priority) &&
      (!f.qtype || it.qtype === f.qtype) &&
      (!f.evidence || (f.evidence === "generated" ? it.is_generated : it.evidence === f.evidence)) &&
      (!q || it.text.toLowerCase().includes(q) || it.topic.toLowerCase().includes(q)));
  }, [data, f]);

  const marksOpts = useMemo(() => Array.from(new Set(data?.items.map((i) => i.marks) || [])).sort((a, b) => a - b), [data]);
  const qtypeOpts = useMemo(() => Array.from(new Set(data?.items.map((i) => i.qtype) || [])), [data]);
  const total = data?.items.length || 0;

  const generate = async () => {
    setGenerating(true);
    try { const r = await api.generatePaper(sid, exam, 0, unitOverride); nav(`/app/papers/${r.id}`); }
    catch (e) { toast(errMsg(e), "error"); } finally { setGenerating(false); }
  };

  const evidenceOpts: (Evidence | "generated")[] = ["exact_repeat", "concept_repeat", "previously_asked", "question_bank", "practice_new", "generated"];

  return (
    <div>
      <PageHeader
        eyebrow={<Link to={`/app/subjects/${sid}`} className="hover:underline">{subject?.name || "Subject"}</Link>}
        title={`${EXAM_LABEL[exam]} predictions`}
        subtitle={data ? `Units ${data.units.join(", ")} · most important questions first` : "Ranking questions from your uploaded papers…"}
        actions={<>
          <button className="btn-outline" onClick={() => downloadFile(`/api/subjects/${sid}/predictions/export?exam_type=${exam}&format=pdf${unitsQ}`, "predictions.pdf").catch((e) => toast(errMsg(e), "error"))}><FileDown className="h-4 w-4" /> PDF</button>
          <button className="btn-outline" onClick={() => downloadFile(`/api/subjects/${sid}/predictions/export?exam_type=${exam}&format=csv${unitsQ}`, "predictions.csv").catch((e) => toast(errMsg(e), "error"))}><Download className="h-4 w-4" /> CSV</button>
          <button className="btn-primary" onClick={generate} disabled={generating || !total}>{generating ? <Spinner /> : <Sparkles className="h-4 w-4" />} Generate paper</button>
        </>}
      />

      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <Segmented<ExamType> value={exam} onChange={(v) => { setParams({ exam: v }); setLimit(30); setUnitOverride(null); }} options={(["CAT1", "CAT2", "SEMESTER"] as ExamType[]).map((t) => ({ id: t, label: EXAM_LABEL[t] }))} />
        {data && <UnitChips all={allUnits} selected={data.units} configured={data.configured_units} onChange={(u) => { setUnitOverride(u); setLimit(30); }} />}
      </div>

      <ReadinessPanel sid={sid} exam={exam} />

      {error && <Notice tone="warn">{error}</Notice>}
      {loading && !data ? (
        <div className="space-y-3"><Skeleton className="h-16" />{[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-36" />)}</div>
      ) : data && (
        <>
          <div className="mb-5 grid gap-3 lg:grid-cols-[1fr_auto]">
            <Notice tone={data.confidence.level === "low" ? "warn" : data.confidence.level === "good" ? "ok" : "info"}>
              <b className="font-semibold">{data.confidence.level === "good" ? "Good" : data.confidence.level === "moderate" ? "Moderate" : "Low"} confidence.</b>{" "}
              {data.confidence.message} <span className="opacity-80">({data.confidence.papers} relevant papers, {data.confidence.same_type_papers} {EXAM_LABEL[exam]})</span>
            </Notice>
            <div className="card flex items-center gap-3 px-4 py-2.5">
              {PRIORITIES.map((p) => (
                <button key={p} onClick={() => setF({ ...f, priority: f.priority === p ? "" : p })} className={`flex items-center gap-1.5 rounded-lg px-1.5 py-0.5 text-xs ${f.priority === p ? "bg-stone-100" : ""}`}>
                  <span className="h-2 w-2 rounded-full" style={{ background: PRIORITY_HEX[p] }} />{PRIORITY_LABEL[p]} <b>{data.counts[p] || 0}</b>
                </button>
              ))}
            </div>
          </div>
          <div className="mb-3"><RankerBadge r={data.ranker} /></div>
          <p className="mb-4 flex items-start gap-2 text-xs muted"><Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />{data.engine.disclaimer}</p>

          <TopicRanking topics={data.topics} onGenerate={setGenTopic} />
          <h3 className="mb-3 font-semibold">Predicted questions</h3>

          <div className="card mb-5 grid gap-2 p-3 sm:grid-cols-3 lg:grid-cols-[1.4fr_repeat(5,1fr)]">
            <div className="relative sm:col-span-3 lg:col-span-1">
              <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-ink-mute" />
              <input className="input pl-9" placeholder="Search questions or topics" value={f.q} onChange={(e) => setF({ ...f, q: e.target.value })} />
            </div>
            <select className="input" value={f.marks} onChange={(e) => setF({ ...f, marks: e.target.value })}><option value="">All marks</option>{marksOpts.map((m) => <option key={m} value={m}>{m} marks</option>)}</select>
            <select className="input" value={f.unit} onChange={(e) => setF({ ...f, unit: e.target.value })}><option value="">All units</option>{data.units.map((u) => <option key={u} value={u}>Unit {u}</option>)}</select>
            <select className="input" value={f.priority} onChange={(e) => setF({ ...f, priority: e.target.value })}><option value="">All priorities</option>{PRIORITIES.map((p) => <option key={p} value={p}>{PRIORITY_LABEL[p]}</option>)}</select>
            <select className="input" value={f.qtype} onChange={(e) => setF({ ...f, qtype: e.target.value })}><option value="">All types</option>{qtypeOpts.map((q) => <option key={q} value={q}>{QTYPE_LABEL[q] || q}</option>)}</select>
            <select className="input" value={f.evidence} onChange={(e) => setF({ ...f, evidence: e.target.value })}>
              <option value="">All evidence</option>
              {evidenceOpts.map((e) => <option key={e} value={e}>{e === "generated" ? "Generated wording only" : EVIDENCE_SHORT[e]}</option>)}
            </select>
          </div>

          {items.length === 0 ? (
            total === 0
              ? <Empty title="Nothing to predict yet" action={<Link className="btn-primary" to={`/app/upload?subject=${sid}`}>Upload papers</Link>}>Upload previous papers or add the syllabus for this subject.</Empty>
              : <Empty title="No questions match these filters" action={<button className="btn-outline" onClick={() => setF({ marks: "", unit: "", priority: "", qtype: "", evidence: "", q: "" })}>Clear filters</button>} />
          ) : (
            <div className="space-y-3">
              <div className="text-xs muted">Showing {Math.min(limit, items.length)} of {items.length}</div>
              {items.slice(0, limit).map((it) => (
                <PredictionCard key={it.id} it={it} rank={data.items.indexOf(it) + 1} weights={data.engine.weights} onPrepare={() => setPreparing(it)} onSave={() => save(it)} />
              ))}
              {limit < items.length && <div className="pt-2 text-center"><button className="btn-outline" onClick={() => setLimit(limit + 30)}>Show more</button></div>}
            </div>
          )}
        </>
      )}
      <PreparePanel subjectId={sid} item={preparing} onClose={() => setPreparing(null)} />
      <GeneratePanel sid={sid} topic={genTopic} exam={exam} onClose={() => setGenTopic(null)} />
    </div>
  );
}
