import { Check, Copy, EyeOff, Pencil, Plus, Search, Trash2, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api, Question, SubjectFull } from "../../api";
import { Empty, errMsg, Modal, Segmented, Skeleton, Spinner, useToast } from "../../components/ui";
import { EXAM_LABEL, QTYPE_LABEL, QTYPES } from "../../lib/format";
import { useAsync } from "../../lib/hooks";

function QuestionEditor({ q, subject, onSave, onCancel }: { q: Partial<Question>; subject: SubjectFull; onSave: (v: Partial<Question>) => void; onCancel: () => void }) {
  const [v, setV] = useState<Partial<Question>>(q);
  const cats = subject.exam_config.mark_categories;
  const topics = subject.units.find((u) => u.number === v.unit)?.topics || [];
  return (
    <div className="space-y-3">
      <div><label className="label">Question text</label><textarea className="input min-h-[90px]" value={v.text || ""} onChange={(e) => setV({ ...v, text: e.target.value })} /></div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div><label className="label">Question slot (marks)</label>
          <select className="input" value={v.category ?? ""} onChange={(e) => setV({ ...v, category: e.target.value ? Number(e.target.value) : null })}>
            <option value="">—</option>{cats.map((c) => <option key={c} value={c}>{c}</option>)}
          </select></div>
        <div><label className="label">Printed marks</label><input className="input" type="number" value={v.marks ?? ""} onChange={(e) => setV({ ...v, marks: e.target.value ? Number(e.target.value) : null })} /></div>
        <div><label className="label">Unit</label>
          <select className="input" value={v.unit ?? ""} onChange={(e) => setV({ ...v, unit: e.target.value ? Number(e.target.value) : null, topic: "" })}>
            <option value="">—</option>{Array.from({ length: Math.max(subject.units.length, subject.exam_config.units_count) }, (_, i) => i + 1).map((u) => <option key={u} value={u}>{u}</option>)}
          </select></div>
        <div><label className="label">Type</label>
          <select className="input" value={v.qtype} onChange={(e) => setV({ ...v, qtype: e.target.value })}>
            {QTYPES.map((t) => <option key={t} value={t}>{QTYPE_LABEL[t]}</option>)}
          </select></div>
      </div>
      <div><label className="label">Topic</label>
        <input className="input" list="topic-options" value={v.topic || ""} onChange={(e) => setV({ ...v, topic: e.target.value })} placeholder="Syllabus topic" />
        <datalist id="topic-options">{topics.map((t) => <option key={t} value={t} />)}</datalist>
      </div>
      <div className="flex justify-end gap-2">
        <button className="btn-outline" onClick={onCancel}>Cancel</button>
        <button className="btn-primary" onClick={() => onSave(v)} disabled={!v.text?.trim()}>Save</button>
      </div>
    </div>
  );
}

function Duplicates({ subject }: { subject: SubjectFull }) {
  const { data, loading } = useAsync(() => api.duplicates(subject.id), [subject.id]);
  if (loading && !data) return <div className="space-y-2">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-28" />)}</div>;
  if (!data?.length) return <Empty icon={<Copy className="h-5 w-5" />} title="No repeated questions found yet">Repeats show up once you've uploaded two or more papers.</Empty>;
  return (
    <div className="space-y-3">
      <p className="text-sm muted">Questions grouped by concept. <b className="text-emerald-700">Exact repeat</b> = asked almost word-for-word in different papers; <b className="text-teal-700">Reworded</b> = same concept, different wording.</p>
      {data.map((g, i) => (
        <div key={i} className="card p-4">
          <div className="mb-2 flex flex-wrap items-center gap-1.5">
            <span className={`chip ${g.exact ? "bg-emerald-50 text-emerald-700" : "bg-teal-50 text-teal-700"}`}>{g.exact ? "Exact repeat" : "Reworded"}</span>
            <span className="chip bg-stone-100 text-ink-soft">{g.papers} paper{g.papers > 1 ? "s" : ""}</span>
            {g.unit && <span className="chip bg-stone-100 text-ink-soft">Unit {g.unit}</span>}
            {g.topic && <span className="chip bg-lav-50 text-lav-700">{g.topic}</span>}
          </div>
          <ul className="space-y-1">
            {g.questions.map((q) => (
              <li key={q.id} className="flex flex-col gap-0.5 text-sm sm:flex-row sm:gap-3">
                <span className="shrink-0 text-xs font-medium text-lav-700 sm:w-40">{EXAM_LABEL[q.exam_type] || (q.doc_kind === "question_bank" ? "Question bank" : "—")} {q.academic_year || q.exam_year || ""} · {q.category}m</span>
                <span className="text-ink-soft">{q.text}</span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

export default function QuestionsTab({ subject }: { subject: SubjectFull }) {
  const { toast, confirm } = useToast();
  const [view, setView] = useState<"all" | "repeats">("all");
  const [f, setF] = useState({ q: "", unit: "", marks: "", exam_type: "", needs_review: false });
  const [debounced, setDebounced] = useState(f);
  useEffect(() => { const t = setTimeout(() => setDebounced(f), 300); return () => clearTimeout(t); }, [f]);
  const { data, loading, reload, setData } = useAsync(() => api.questions(subject.id, debounced), [subject.id, debounced]);
  const { data: docs } = useAsync(() => api.documents(subject.id), [subject.id]);
  const [editing, setEditing] = useState<Question | null>(null);
  const [adding, setAdding] = useState<{ docId: number | "" } | null>(null);
  const unitCount = Math.max(subject.units.length, subject.exam_config.units_count);

  const patch = async (q: Question, b: Partial<Question>, msg = "Saved") => {
    try {
      const updated = await api.patchQuestion(q.id, b);
      setData((d) => d && d.map((x) => (x.id === q.id ? updated : x)));
      toast(msg);
    } catch (e) { toast(errMsg(e), "error"); }
  };

  const paperDocs = useMemo(() => (docs || []).filter((d) => d.kind !== "syllabus"), [docs]);

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <Segmented value={view} onChange={setView} options={[{ id: "all", label: "All questions" }, { id: "repeats", label: "Repeated questions" }]} />
        {view === "all" && paperDocs.length > 0 && <button className="btn-outline btn-sm" onClick={() => setAdding({ docId: paperDocs[0].id })}><Plus className="h-3.5 w-3.5" /> Add question</button>}
      </div>
      {view === "repeats" ? <Duplicates subject={subject} /> : (
        <>
          <div className="card mb-4 grid gap-2 p-3 sm:grid-cols-[1fr_auto_auto_auto_auto] sm:items-center">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-ink-mute" />
              <input className="input pl-9" placeholder="Search by keyword or concept…" value={f.q} onChange={(e) => setF({ ...f, q: e.target.value })} />
            </div>
            <select className="input sm:w-28" value={f.unit} onChange={(e) => setF({ ...f, unit: e.target.value })}>
              <option value="">All units</option>{Array.from({ length: unitCount }, (_, i) => <option key={i} value={i + 1}>Unit {i + 1}</option>)}
            </select>
            <select className="input sm:w-28" value={f.marks} onChange={(e) => setF({ ...f, marks: e.target.value })}>
              <option value="">All marks</option>{subject.exam_config.mark_categories.map((m) => <option key={m} value={m}>{m} marks</option>)}
            </select>
            <select className="input sm:w-32" value={f.exam_type} onChange={(e) => setF({ ...f, exam_type: e.target.value })}>
              <option value="">All exams</option><option value="CAT1">CAT 1</option><option value="CAT2">CAT 2</option><option value="SEMESTER">Semester</option>
            </select>
            <label className="flex items-center gap-2 whitespace-nowrap px-1 text-sm text-ink-soft">
              <input type="checkbox" className="accent-lav-500" checked={f.needs_review} onChange={(e) => setF({ ...f, needs_review: e.target.checked })} /> Needs review
            </label>
          </div>

          {loading && !data ? <div className="space-y-2">{[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-16" />)}</div>
            : !data?.length ? <Empty title="No questions match">Try clearing filters, or upload papers to extract questions.</Empty>
              : (
                <div className="card divide-y divide-line">
                  <div className="px-4 py-2 text-xs muted">{data.length} question{data.length > 1 ? "s" : ""}{loading && <Spinner className="ml-2 inline" />}</div>
                  {data.map((q) => {
                    const weak = !q.verified && q.confidence < 0.6;
                    return (
                      <div key={q.id} className={`flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-start ${q.excluded ? "opacity-50" : ""}`}>
                        <div className="w-full shrink-0 text-xs muted sm:w-36">
                          <div className="font-medium text-ink-soft">{q.doc_kind === "question_bank" ? "Question bank" : `${EXAM_LABEL[q.exam_type] || "—"} ${q.academic_year || q.exam_year || ""}`}</div>
                          <div>Q{q.number}{q.choice && ` (${q.choice})`}{q.sub && ` (${q.sub})`}{q.co && ` · ${q.co}`}</div>
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="text-sm">{q.text}</p>
                          <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-xs">
                            <span className="chip bg-stone-100 text-ink-soft">{q.category ?? "?"} marks{q.marks && q.marks !== q.category ? ` (part: ${q.marks})` : ""}</span>
                            <span className={`chip ${q.unit ? "bg-stone-100 text-ink-soft" : "bg-amber-50 text-amber-700"}`}>{q.unit ? `Unit ${q.unit}` : "Unit unknown"}</span>
                            {q.topic ? <span className="chip bg-lav-50 text-lav-700">{q.topic}{q.subtopic ? ` › ${q.subtopic}` : ""}</span> : <span className="chip bg-stone-50 text-ink-mute">No topic match</span>}
                            {q.topic && q.topic_source && <span className="chip bg-stone-50 text-ink-mute" title="How this topic was assigned">{q.topic_source === "keyword" ? "via keyword" : q.topic_source === "manual" ? "set by you" : q.topic_source === "discovered" ? "discovered topic" : "via syllabus match"}</span>}
                            <span className="chip bg-stone-50 text-ink-mute">{QTYPE_LABEL[q.qtype] || q.qtype}</span>
                            {q.verified && <span className="chip bg-emerald-50 text-emerald-700"><Check className="h-3 w-3" /> Checked</span>}
                            {weak && <span className="chip bg-amber-50 text-amber-700">Check extraction</span>}
                            {q.excluded && <span className="chip bg-stone-200 text-ink-soft">Excluded from predictions</span>}
                            {q.is_sample && <span className="chip bg-amber-50 text-amber-700">Sample</span>}
                          </div>
                        </div>
                        <div className="flex shrink-0 gap-0.5">
                          {!q.verified && <button className="btn-ghost btn-sm" title="Mark as checked" onClick={() => patch(q, { verified: true }, "Marked as checked")}><Check className="h-3.5 w-3.5" /></button>}
                          <button className="btn-ghost btn-sm" title="Edit" onClick={() => setEditing(q)}><Pencil className="h-3.5 w-3.5" /></button>
                          <button className="btn-ghost btn-sm" title={q.excluded ? "Include in predictions" : "Exclude from predictions"} onClick={() => patch(q, { excluded: !q.excluded }, q.excluded ? "Included" : "Excluded")}>
                            {q.excluded ? <X className="h-3.5 w-3.5" /> : <EyeOff className="h-3.5 w-3.5" />}
                          </button>
                          <button className="btn-ghost btn-sm text-rose-600" title="Delete" onClick={async () => {
                            if (await confirm("Delete this question?")) {
                              try { await api.deleteQuestion(q.id); setData((d) => d && d.filter((x) => x.id !== q.id)); } catch (e) { toast(errMsg(e), "error"); }
                            }
                          }}><Trash2 className="h-3.5 w-3.5" /></button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
        </>
      )}

      <Modal open={!!editing} onClose={() => setEditing(null)} title="Edit question" wide>
        {editing && <QuestionEditor q={editing} subject={subject} onCancel={() => setEditing(null)} onSave={(v) => {
          const q = editing; setEditing(null);
          patch(q, { text: v.text, category: v.category, marks: v.marks, unit: v.unit, topic: v.topic, qtype: v.qtype });
        }} />}
      </Modal>

      <Modal open={!!adding} onClose={() => setAdding(null)} title="Add a question" wide>
        {adding && (
          <div className="space-y-3">
            <div><label className="label">Add to document</label>
              <select className="input" value={adding.docId} onChange={(e) => setAdding({ docId: Number(e.target.value) })}>
                {paperDocs.map((d) => <option key={d.id} value={d.id}>{d.filename}</option>)}
              </select></div>
            <QuestionEditor q={{ text: "", qtype: "theory", category: subject.exam_config.mark_categories[0] }} subject={subject} onCancel={() => setAdding(null)} onSave={async (v) => {
              const docId = Number(adding.docId); setAdding(null);
              try {
                await api.addQuestion(docId, { text: v.text!, category: v.category, marks: v.marks ?? v.category, unit: v.unit, topic: v.topic || "", qtype: v.qtype });
                toast("Question added"); reload(true);
              } catch (e) { toast(errMsg(e), "error"); }
            }} />
          </div>
        )}
      </Modal>
    </div>
  );
}
