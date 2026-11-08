import { CheckCircle2, Layers, ScanText, Sparkles, Tags } from "lucide-react";
import { useState } from "react";
import { api, DiscoveredTopic, Discovery, Question, SubjectFull, Suggestion } from "../../api";
import { Empty, errMsg, Notice, Skeleton, Spinner, useToast } from "../../components/ui";
import { EXAM_LABEL } from "../../lib/format";
import { useAsync } from "../../lib/hooks";

function TopicPicker({ subject, onPick, busy, initial }: { subject: SubjectFull; onPick: (unit: number, topic: string) => void; busy?: boolean; initial?: Suggestion | null }) {
  const [unit, setUnit] = useState<number>(initial?.unit || subject.units[0]?.number || 1);
  const topics = subject.units.find((u) => u.number === unit)?.topics || [];
  const [topic, setTopic] = useState<string>(initial?.topic || topics[0] || "");
  return (
    <div className="flex flex-wrap items-center gap-2">
      <select className="input w-auto" value={unit} onChange={(e) => { const u = Number(e.target.value); setUnit(u); setTopic(subject.units.find((x) => x.number === u)?.topics[0] || ""); }}>
        {subject.units.map((u) => <option key={u.number} value={u.number}>Unit {u.number}</option>)}
      </select>
      <select className="input w-auto min-w-0 max-w-[16rem]" value={topic} onChange={(e) => setTopic(e.target.value)}>
        {topics.map((t) => <option key={t} value={t}>{t}</option>)}
      </select>
      <button className="btn-outline btn-sm" disabled={busy || !topic} onClick={() => onPick(unit, topic)}>{busy && <Spinner />} Assign</button>
    </div>
  );
}

function Meta({ q }: { q: Question }) {
  return (
    <div className="text-xs muted">
      {EXAM_LABEL[q.exam_type] || q.doc_kind.replace("_", " ")} {q.academic_year || q.exam_year || ""} · Q{q.number}{q.choice ? `(${q.choice})` : ""} · {q.category || "?"} marks{q.unit ? ` · Unit ${q.unit}` : ""}
    </div>
  );
}

function DiscoveredCard({ t, subject, onDone }: { t: DiscoveredTopic; subject: SubjectFull; onDone: () => void }) {
  const { toast } = useToast();
  const [mode, setMode] = useState<"existing" | "new">(t.suggested_topic ? "existing" : "new");
  const [name, setName] = useState(t.label);
  const [unit, setUnit] = useState<number>(t.unit || t.suggested_topic?.unit || subject.units[0]?.number || 1);
  const [busy, setBusy] = useState(false);
  const apply = async (u: number, topic: string, create: boolean) => {
    setBusy(true);
    try {
      const r = await api.applyDiscovery(subject.id, { question_ids: t.question_ids, unit: u, topic, create_topic: create, keywords: t.keywords.slice(0, 3) });
      toast(`${r.assigned} question(s) assigned to “${topic}”`);
      onDone();
    } catch (e) { toast(errMsg(e), "error"); } finally { setBusy(false); }
  };
  return (
    <div className="rounded-xl border border-line bg-white p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-semibold">{t.label}</span>
        <span className="chip bg-stone-100 text-ink-soft">{t.question_ids.length} questions</span>
        {t.unit && <span className="chip bg-stone-100 text-ink-soft">Unit {t.unit}</span>}
      </div>
      {t.keywords.length > 0 && <div className="mt-1 text-xs muted">Keywords: {t.keywords.join(", ")}</div>}
      <ul className="mt-2 space-y-1 text-sm text-ink-soft">{t.examples.map((e, i) => <li key={i}>• {e}</li>)}</ul>
      <div className="mt-3 flex flex-wrap gap-1.5 text-xs">
        <button className={`chip ${mode === "existing" ? "bg-ink text-white" : "bg-stone-100 text-ink-soft"}`} onClick={() => setMode("existing")}>Assign to existing topic</button>
        <button className={`chip ${mode === "new" ? "bg-ink text-white" : "bg-stone-100 text-ink-soft"}`} onClick={() => setMode("new")}>Add as new syllabus topic</button>
      </div>
      <div className="mt-2">
        {mode === "existing" ? (
          <>
            {t.suggested_topic && <p className="mb-1.5 text-xs muted">Suggested: Unit {t.suggested_topic.unit} · {t.suggested_topic.topic}</p>}
            <TopicPicker subject={subject} initial={t.suggested_topic} busy={busy} onPick={(u, tp) => apply(u, tp, false)} />
          </>
        ) : (
          <div className="flex flex-wrap items-center gap-2">
            <input className="input w-auto min-w-0 flex-1" value={name} onChange={(e) => setName(e.target.value)} placeholder="Topic name" />
            <select className="input w-auto" value={unit} onChange={(e) => setUnit(Number(e.target.value))}>
              {subject.units.map((u) => <option key={u.number} value={u.number}>Unit {u.number}</option>)}
            </select>
            <button className="btn-outline btn-sm" disabled={busy || !name.trim()} onClick={() => apply(unit, name.trim(), true)}>{busy && <Spinner />} Add & assign</button>
          </div>
        )}
      </div>
    </div>
  );
}

export default function ReviewTab({ subject, onChange }: { subject: SubjectFull; onChange: () => void }) {
  const { toast } = useToast();
  const { data, loading, error, reload } = useAsync(() => api.review(subject.id), [subject.id]);
  const [busy, setBusy] = useState<number | null>(null);
  const [edits, setEdits] = useState<Record<number, string>>({});
  const [disc, setDisc] = useState<Discovery | null>(null);
  const [discovering, setDiscovering] = useState(false);

  const refresh = () => { reload(true); onChange(); };
  const assign = async (qid: number, unit: number, topic: string) => {
    setBusy(qid);
    try { await api.patchQuestion(qid, { unit, topic }); toast(`Mapped to ${topic}`); refresh(); } catch (e) { toast(errMsg(e), "error"); } finally { setBusy(null); }
  };
  const verify = async (q: Question) => {
    setBusy(q.id);
    try {
      const text = edits[q.id];
      await api.patchQuestion(q.id, text !== undefined && text !== q.text ? { text, verified: true } : { verified: true });
      toast("Marked as checked"); refresh();
    } catch (e) { toast(errMsg(e), "error"); } finally { setBusy(null); }
  };
  const discover = async () => {
    setDiscovering(true);
    try { setDisc(await api.discover(subject.id)); } catch (e) { toast(errMsg(e), "error"); } finally { setDiscovering(false); }
  };

  if (error) return <Notice tone="warn">{error}</Notice>;
  if (loading && !data) return <div className="space-y-3"><Skeleton className="h-24" /><Skeleton className="h-48" /></div>;
  if (!data) return null;

  return (
    <div className="space-y-5">
      <div className="card p-5">
        <h3 className="flex items-center gap-2 font-semibold"><CheckCircle2 className="h-4 w-4 text-lav-500" /> Review queue</h3>
        <p className="mt-1 max-w-3xl text-sm muted">
          Questions the system wasn't sure about. Mapping them to syllabus topics and fixing uncertain extractions makes topic rankings and predictions more accurate. Your corrections are never overwritten.
        </p>
      </div>

      {!data.has_syllabus && <Notice tone="warn">No syllabus yet — add one in the Syllabus tab so questions can be mapped to topics.</Notice>}

      <section>
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h3 className="flex items-center gap-2 font-semibold"><Tags className="h-4 w-4 text-lav-500" /> Missing or weak topic mapping <span className="chip bg-stone-100 text-ink-soft">{data.unmapped.length}</span></h3>
          {data.has_syllabus && <button className="btn-outline btn-sm" onClick={discover} disabled={discovering}>{discovering ? <Spinner /> : <Sparkles className="h-3.5 w-3.5" />} Discover topics</button>}
        </div>
        {data.unmapped.length === 0 ? <p className="text-sm muted">All questions are mapped to syllabus topics.</p> : (
          <div className="space-y-2">
            {data.unmapped.map((q) => (
              <div key={q.id} className="rounded-xl border border-line bg-white p-3">
                <Meta q={q} />
                <p className="mt-1 text-sm">{q.text}</p>
                {q.topic && <p className="mt-0.5 text-xs text-amber-700">Currently “{q.topic}” with low confidence</p>}
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  {q.suggestions.filter((s) => s.score > 0).map((s) => (
                    <button key={`${s.unit}-${s.topic}`} className="chip bg-lav-50 text-lav-700 ring-1 ring-lav-200 hover:bg-lav-100" disabled={busy === q.id}
                      onClick={() => assign(q.id, s.unit, s.topic)}>U{s.unit} · {s.topic}</button>
                  ))}
                </div>
                {data.has_syllabus && <div className="mt-2"><TopicPicker subject={subject} busy={busy === q.id} onPick={(u, t) => assign(q.id, u, t)} /></div>}
              </div>
            ))}
          </div>
        )}
      </section>

      {disc && (
        <section className="card p-5">
          <h3 className="flex items-center gap-2 font-semibold"><Layers className="h-4 w-4 text-lav-500" /> Discovered topics</h3>
          <p className="mt-0.5 text-sm muted">
            Grouped {disc.unclassified} unmapped question(s) using {disc.method === "BERTopic" ? "BERTopic" : "built-in semantic clustering"}. Nothing changes until you accept a group.
          </p>
          {disc.topics.length === 0 ? <p className="mt-3 text-sm muted">No groups of similar questions found.</p> : (
            <div className="mt-3 space-y-3">{disc.topics.map((t, i) => <DiscoveredCard key={i} t={t} subject={subject} onDone={() => { discover(); refresh(); }} />)}</div>
          )}
          {disc.unclustered.length > 0 && <p className="mt-3 text-xs muted">{disc.unclustered.length} question(s) didn't fit any group — map them individually above.</p>}
        </section>
      )}

      <section>
        <h3 className="mb-2 flex items-center gap-2 font-semibold"><ScanText className="h-4 w-4 text-lav-500" /> Uncertain extractions <span className="chip bg-stone-100 text-ink-soft">{data.uncertain.length}</span></h3>
        {data.uncertain.length === 0 ? <p className="text-sm muted">No uncertain extractions.</p> : (
          <div className="space-y-2">
            {data.uncertain.map((q) => (
              <div key={q.id} className="rounded-xl border border-line bg-white p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Meta q={q} />
                  {q.ocr && <span className="chip bg-amber-50 text-amber-700">OCR</span>}
                  <span className="chip bg-stone-100 text-ink-soft">confidence {Math.round(q.confidence * 100)}%</span>
                </div>
                <textarea className="input mt-2 min-h-[64px]" value={edits[q.id] ?? q.text} onChange={(e) => setEdits({ ...edits, [q.id]: e.target.value })} />
                <div className="mt-2 flex justify-end">
                  <button className="btn-outline btn-sm" disabled={busy === q.id} onClick={() => verify(q)}>{busy === q.id && <Spinner />} {edits[q.id] !== undefined && edits[q.id] !== q.text ? "Save & mark checked" : "Looks right"}</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {data.unmapped.length === 0 && data.uncertain.length === 0 && (
        <Empty title="Nothing waiting for review">Every question is mapped and every extraction looks confident.</Empty>
      )}
    </div>
  );
}
