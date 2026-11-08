import { CalendarPlus, CheckCircle2, Plus, Sparkles, Trash2, Wand2 } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";
import { api, Saved, TopicStatus } from "../api";
import { Bar, Empty, errMsg, Modal, PageHeader, Skeleton, Spinner, Stat, useToast } from "../components/ui";
import { EXAM_LABEL, EXAM_TYPES, PRIORITY_STYLE, STATUS_LABEL, STATUS_STYLE, STATUSES, todayISO } from "../lib/format";
import { useAsync } from "../lib/hooks";

function SavedRow({ s, onChange, onDelete }: { s: Saved; onChange: (v: Partial<Saved>) => void; onDelete: () => void }) {
  const [note, setNote] = useState(s.note);
  return (
    <div className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-start">
      <div className="min-w-0 flex-1">
        <p className="text-sm">{s.text}</p>
        <div className="mt-1 flex flex-wrap gap-1.5 text-xs">
          <span className="chip bg-stone-100 text-ink-soft">{s.subject}</span>
          {s.marks && <span className="chip bg-stone-100 text-ink-soft">{s.marks} marks</span>}
          {s.unit && <span className="chip bg-stone-100 text-ink-soft">Unit {s.unit}</span>}
          {s.priority && s.priority in PRIORITY_STYLE && <span className={`chip ${PRIORITY_STYLE[s.priority as keyof typeof PRIORITY_STYLE]}`}>{s.priority.replace("_", " ")}</span>}
          {s.evidence === "practice_new" && <span className="chip border border-dashed border-orange-300 bg-orange-50 text-orange-700">Generated</span>}
        </div>
        <input className="mt-2 w-full rounded-lg border border-transparent bg-transparent px-2 py-1 text-xs text-ink-soft placeholder:text-ink-mute hover:border-line focus:border-lav-200 focus:bg-white focus:outline-none"
          placeholder="Add a note…" value={note} onChange={(e) => setNote(e.target.value)} onBlur={() => note !== s.note && onChange({ note })} />
      </div>
      <div className="flex shrink-0 items-center gap-1">
        <select value={s.status} onChange={(e) => onChange({ status: e.target.value as TopicStatus })} className={`rounded-full border-0 px-2.5 py-1 text-xs font-medium ${STATUS_STYLE[s.status]}`}>
          {STATUSES.map((st) => <option key={st} value={st}>{STATUS_LABEL[st]}</option>)}
        </select>
        <button className="btn-ghost btn-sm text-rose-600" onClick={onDelete}><Trash2 className="h-3.5 w-3.5" /></button>
      </div>
    </div>
  );
}

export default function Planner() {
  const { toast, confirm } = useToast();
  const { data: subjects } = useAsync(() => api.subjects(), []);
  const exams = useAsync(() => api.exams(), []);
  const plan = useAsync(() => api.plan(), []);
  const saved = useAsync(() => api.saved(), []);
  const [subjectFilter, setSubjectFilter] = useState<number | "">("");
  const [auto, setAuto] = useState<{ exam_id: number | ""; minutes: number; busy: boolean } | null>(null);
  const [adding, setAdding] = useState<{ date: string; title: string; subject_id: number | ""; minutes: number } | null>(null);
  const [examForm, setExamForm] = useState<{ subject_id: number | ""; exam_type: string; date: string } | null>(null);
  const [showPast, setShowPast] = useState(false);

  const today = todayISO();
  const grouped = useMemo(() => {
    const g: Record<string, typeof plan.data> = {};
    (plan.data || []).filter((p) => showPast || p.date >= today).forEach((p) => { (g[p.date] = g[p.date] || []).push(p); });
    return Object.entries(g).sort(([a], [b]) => a.localeCompare(b));
  }, [plan.data, showPast, today]);

  const savedList = (saved.data || []).filter((s) => !subjectFilter || s.subject_id === subjectFilter);
  const doneSaved = (saved.data || []).filter((s) => s.status === "completed").length;
  const planTotal = (plan.data || []).length;
  const planDone = (plan.data || []).filter((p) => p.done).length;

  const runAuto = async () => {
    if (!auto?.exam_id) return;
    setAuto({ ...auto, busy: true });
    try {
      const items = await api.autoPlan(Number(auto.exam_id), auto.minutes);
      toast(`Added ${items.length} study sessions`);
      setAuto(null);
      plan.reload(true);
    } catch (e) { toast(errMsg(e), "error"); setAuto({ ...auto, busy: false }); }
  };

  const addItem = async (e: FormEvent) => {
    e.preventDefault();
    if (!adding?.title.trim()) return;
    try {
      await api.addPlan({ date: adding.date, title: adding.title, subject_id: adding.subject_id ? Number(adding.subject_id) : null, unit: null, minutes: adding.minutes });
      setAdding(null); plan.reload(true);
    } catch (err) { toast(errMsg(err), "error"); }
  };

  const addExam = async (e: FormEvent) => {
    e.preventDefault();
    if (!examForm?.subject_id) return;
    try {
      await api.addExam({ subject_id: Number(examForm.subject_id), exam_type: examForm.exam_type, date: examForm.date, title: "" });
      setExamForm(null); exams.reload(true);
    } catch (err) { toast(errMsg(err), "error"); }
  };

  return (
    <div>
      <PageHeader title="Study planner" subtitle="Organise preparation around predicted questions and your exam dates."
        actions={<>
          <button className="btn-outline" onClick={() => setAdding({ date: today, title: "", subject_id: subjects?.[0]?.id ?? "", minutes: 60 })}><Plus className="h-4 w-4" /> Add session</button>
          <button className="btn-primary" onClick={() => setAuto({ exam_id: exams.data?.find((e) => e.days_left > 0)?.id ?? "", minutes: 120, busy: false })}><Wand2 className="h-4 w-4" /> Auto-plan for an exam</button>
        </>} />

      <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Upcoming exams" value={(exams.data || []).filter((e) => e.days_left >= 0).length} />
        <Stat label="Next exam in" value={(() => { const n = (exams.data || []).find((e) => e.days_left >= 0); return n ? `${n.days_left} days` : "—"; })()} />
        <Stat label="Sessions done" value={`${planDone}/${planTotal}`} hint={<Bar value={planTotal ? (100 * planDone) / planTotal : 0} className="bg-emerald-500" />} />
        <Stat label="Saved questions prepared" value={`${doneSaved}/${saved.data?.length || 0}`} hint={<Bar value={saved.data?.length ? (100 * doneSaved) / saved.data.length : 0} className="bg-lav-500" />} />
      </div>

      <div className="grid gap-5 lg:grid-cols-[1fr_320px]">
        <section>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-semibold">Plan</h2>
            <label className="flex items-center gap-2 text-xs muted"><input type="checkbox" className="accent-lav-500" checked={showPast} onChange={(e) => setShowPast(e.target.checked)} /> Show past days</label>
          </div>
          {plan.loading && !plan.data ? <Skeleton className="h-48" /> : grouped.length === 0 ? (
            <Empty icon={<CalendarPlus className="h-5 w-5" />} title="No study sessions planned"
              action={<button className="btn-primary" onClick={() => setAuto({ exam_id: exams.data?.[0]?.id ?? "", minutes: 120, busy: false })}><Sparkles className="h-4 w-4" /> Auto-plan from predictions</button>}>
              Add an exam date, then let the planner spread the highest-priority predicted questions over the days you have.
            </Empty>
          ) : (
            <div className="space-y-4">
              {grouped.map(([date, items]) => {
                const d = new Date(date + "T00:00");
                const isToday = date === today;
                return (
                  <div key={date} className="card overflow-hidden">
                    <div className={`flex items-center justify-between px-4 py-2 text-sm ${isToday ? "bg-lav-50 text-lav-700" : "bg-stone-50"}`}>
                      <span className="font-medium">{isToday ? "Today" : d.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "short" })}</span>
                      <span className="text-xs muted">{items!.reduce((s, i) => s + i.minutes, 0)} min</span>
                    </div>
                    <ul className="divide-y divide-line">
                      {items!.map((p) => (
                        <li key={p.id} className="group flex items-start gap-3 px-4 py-2.5">
                          <input type="checkbox" className="mt-1 accent-lav-500" checked={p.done} onChange={async () => {
                            plan.setData((all) => all && all.map((x) => x.id === p.id ? { ...x, done: !p.done } : x));
                            try { await api.patchPlan(p.id, { done: !p.done }); } catch (e) { toast(errMsg(e), "error"); }
                          }} />
                          <div className="min-w-0 flex-1">
                            <div className={`text-sm ${p.done ? "line-through muted" : ""}`}>{p.title}</div>
                            <div className="text-xs muted">{p.minutes} min{p.subject ? ` · ${p.subject}` : ""}</div>
                          </div>
                          <button className="btn-ghost btn-sm text-rose-600 sm:opacity-0 sm:group-hover:opacity-100" onClick={async () => { await api.deletePlan(p.id); plan.reload(true); }}><Trash2 className="h-3.5 w-3.5" /></button>
                        </li>
                      ))}
                    </ul>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        <aside className="space-y-5">
          <div className="card p-5">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="font-semibold">Exams</h2>
              <button className="btn-ghost btn-sm" onClick={() => setExamForm({ subject_id: subjects?.[0]?.id ?? "", exam_type: "CAT1", date: todayISO(14) })} disabled={!subjects?.length}><Plus className="h-3.5 w-3.5" /> Add</button>
            </div>
            {!exams.data?.length ? <p className="text-sm muted">No exams yet.</p> : (
              <ul className="space-y-2">
                {exams.data.map((e) => (
                  <li key={e.id} className="flex items-center gap-3">
                    <div className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl text-center ${e.days_left < 0 ? "bg-stone-100 text-stone-400" : e.days_left <= 7 ? "bg-amber-50 text-amber-700" : "bg-lav-50 text-lav-700"}`}>
                      <div className="text-sm font-semibold leading-none">{e.days_left < 0 ? "✓" : e.days_left}</div>
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm">{EXAM_LABEL[e.exam_type]} · {e.subject}</div>
                      <div className="text-xs muted">{e.date}</div>
                    </div>
                    <button className="btn-ghost btn-sm" onClick={async () => { if (await confirm("Remove this exam?", "Remove")) { await api.deleteExam(e.id); exams.reload(true); } }}><Trash2 className="h-3.5 w-3.5" /></button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </aside>
      </div>

      <section className="mt-8">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="flex items-center gap-2 font-semibold"><CheckCircle2 className="h-4 w-4 text-lav-500" /> Saved questions</h2>
          <select className="input w-auto" value={subjectFilter} onChange={(e) => setSubjectFilter(e.target.value ? Number(e.target.value) : "")}>
            <option value="">All subjects</option>{subjects?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </div>
        {saved.loading && !saved.data ? <Skeleton className="h-32" /> : savedList.length === 0 ? (
          <Empty title="No saved questions">Use “Save” on any predicted question to build your personal study list.</Empty>
        ) : (
          <div className="card divide-y divide-line">
            {savedList.map((s) => (
              <SavedRow key={s.id} s={s}
                onChange={async (v) => {
                  try { const u = await api.patchSaved(s.id, v); saved.setData((all) => all && all.map((x) => (x.id === s.id ? u : x))); } catch (e) { toast(errMsg(e), "error"); }
                }}
                onDelete={async () => { await api.deleteSaved(s.id); saved.setData((all) => all && all.filter((x) => x.id !== s.id)); }} />
            ))}
          </div>
        )}
      </section>

      <Modal open={!!auto} onClose={() => setAuto(null)} title="Auto-plan for an exam">
        {auto && (!exams.data?.filter((e) => e.days_left > 1).length ? (
          <div className="space-y-3">
            <p className="text-sm muted">Add an upcoming exam (at least 2 days away) first.</p>
            <button className="btn-primary" onClick={() => { setAuto(null); setExamForm({ subject_id: subjects?.[0]?.id ?? "", exam_type: "CAT1", date: todayISO(14) }); }}>Add an exam</button>
          </div>
        ) : (
          <div className="space-y-3">
            <div><label className="label">Exam</label>
              <select className="input" value={auto.exam_id} onChange={(e) => setAuto({ ...auto, exam_id: Number(e.target.value) })}>
                <option value="">Choose…</option>
                {exams.data!.filter((e) => e.days_left > 1).map((e) => <option key={e.id} value={e.id}>{EXAM_LABEL[e.exam_type]} · {e.subject} · {e.date}</option>)}
              </select></div>
            <div><label className="label">Study time per day: {auto.minutes} min</label>
              <input type="range" min={30} max={360} step={15} className="w-full accent-lav-500" value={auto.minutes} onChange={(e) => setAuto({ ...auto, minutes: Number(e.target.value) })} /></div>
            <p className="text-xs muted">Very-high and high priority questions are scheduled first, grouped by unit, with a revision day before the exam.</p>
            <div className="flex justify-end"><button className="btn-primary" onClick={runAuto} disabled={!auto.exam_id || auto.busy}>{auto.busy && <Spinner />} Create plan</button></div>
          </div>
        ))}
      </Modal>

      <Modal open={!!adding} onClose={() => setAdding(null)} title="Add study session">
        {adding && (
          <form onSubmit={addItem} className="space-y-3">
            <div><label className="label">What will you study?</label><input className="input" required value={adding.title} onChange={(e) => setAdding({ ...adding, title: e.target.value })} placeholder="e.g. Unit 3 — IPv6 and subnetting problems" /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><label className="label">Date</label><input className="input" type="date" value={adding.date} onChange={(e) => setAdding({ ...adding, date: e.target.value })} /></div>
              <div><label className="label">Minutes</label><input className="input" type="number" min={10} value={adding.minutes} onChange={(e) => setAdding({ ...adding, minutes: Number(e.target.value) })} /></div>
            </div>
            <div><label className="label">Subject</label>
              <select className="input" value={adding.subject_id} onChange={(e) => setAdding({ ...adding, subject_id: e.target.value ? Number(e.target.value) : "" })}>
                <option value="">—</option>{subjects?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select></div>
            <div className="flex justify-end"><button className="btn-primary">Add</button></div>
          </form>
        )}
      </Modal>

      <Modal open={!!examForm} onClose={() => setExamForm(null)} title="Add exam">
        {examForm && (
          <form onSubmit={addExam} className="space-y-3">
            <div><label className="label">Subject</label>
              <select className="input" value={examForm.subject_id} onChange={(e) => setExamForm({ ...examForm, subject_id: Number(e.target.value) })}>
                {subjects?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select></div>
            <div className="grid grid-cols-2 gap-3">
              <div><label className="label">Exam</label>
                <select className="input" value={examForm.exam_type} onChange={(e) => setExamForm({ ...examForm, exam_type: e.target.value })}>
                  {EXAM_TYPES.map((t) => <option key={t} value={t}>{EXAM_LABEL[t]}</option>)}
                </select></div>
              <div><label className="label">Date</label><input className="input" type="date" min={today} value={examForm.date} onChange={(e) => setExamForm({ ...examForm, date: e.target.value })} /></div>
            </div>
            <div className="flex justify-end"><button className="btn-primary">Add exam</button></div>
          </form>
        )}
      </Modal>
    </div>
  );
}
