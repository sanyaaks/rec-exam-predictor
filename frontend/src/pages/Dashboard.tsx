import { ArrowRight, BookOpen, CalendarClock, CheckCircle2, FileText, Plus, Sparkles, Trash2, Upload, Wand2 } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, auth, ExamType } from "../api";
import { Bar, Empty, errMsg, Notice, PageHeader, Skeleton, Spinner, useToast } from "../components/ui";
import { DOC_STATUS_LABEL, DOC_STATUS_STYLE, EXAM_LABEL, EXAM_TYPES, KIND_LABEL, relTime, todayISO } from "../lib/format";
import { useAsync, useMeta } from "../lib/hooks";

export default function Dashboard() {
  const nav = useNavigate();
  const { toast, confirm } = useToast();
  const meta = useMeta();
  const { data, loading, error, reload } = useAsync(() => api.dashboard(), []);
  const user = auth.user();

  const [qp, setQp] = useState<{ subject: number | ""; exam: ExamType }>({ subject: "", exam: "SEMESTER" });
  const [generating, setGenerating] = useState(false);
  const [examForm, setExamForm] = useState({ subject_id: "" as number | "", exam_type: "CAT1", date: todayISO(14) });
  const [showExam, setShowExam] = useState(false);

  useEffect(() => {
    if (data?.subjects.length && qp.subject === "") setQp((q) => ({ ...q, subject: data.subjects[0].id }));
    if (data?.subjects.length && examForm.subject_id === "") setExamForm((f) => ({ ...f, subject_id: data.subjects[0].id }));
  }, [data]); // eslint-disable-line react-hooks/exhaustive-deps

  const generate = async () => {
    if (!qp.subject) return;
    setGenerating(true);
    try {
      const r = await api.generatePaper(Number(qp.subject), qp.exam);
      nav(`/app/papers/${r.id}`);
    } catch (e) {
      toast(errMsg(e), "error");
    } finally {
      setGenerating(false);
    }
  };

  const addExam = async (e: FormEvent) => {
    e.preventDefault();
    if (!examForm.subject_id) return;
    try {
      await api.addExam({ subject_id: Number(examForm.subject_id), exam_type: examForm.exam_type, date: examForm.date, title: "" });
      setShowExam(false);
      reload(true);
      toast("Exam added");
    } catch (err) {
      toast(errMsg(err), "error");
    }
  };

  const hour = new Date().getHours();
  const greet = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";

  return (
    <div>
      <PageHeader
        eyebrow={new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" })}
        title={`${greet}, ${user?.name?.split(" ")[0] || "there"}`}
        subtitle="Here's where your preparation stands."
        actions={<><Link to="/app/upload" className="btn-outline"><Upload className="h-4 w-4" /> Upload papers</Link><Link to="/app/subjects" className="btn-primary"><Plus className="h-4 w-4" /> New subject</Link></>}
      />

      {meta && meta.limitations.length > 0 && (
        <div className="mb-6"><Notice>{meta.limitations.join(" ")}</Notice></div>
      )}
      {error && <Notice tone="warn">{error}</Notice>}

      {loading && !data ? (
        <div className="grid gap-4 lg:grid-cols-3"><Skeleton className="h-48 lg:col-span-2" /><Skeleton className="h-48" /><Skeleton className="h-40" /><Skeleton className="h-40 lg:col-span-2" /></div>
      ) : data && (
        <div className="grid gap-5 lg:grid-cols-3">
          {/* quick prediction */}
          <section className="card relative overflow-hidden p-5 lg:col-span-2">
            <div className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-gradient-to-br from-lav-200/70 to-sky2-100/40 blur-2xl" />
            <div className="relative">
              <div className="flex items-center gap-2 text-sm font-medium text-lav-700"><Wand2 className="h-4 w-4" /> Quick prediction</div>
              <h2 className="mt-1 text-lg font-semibold">Generate a predicted question paper</h2>
              {data.subjects.length === 0 ? (
                <p className="mt-2 text-sm muted">Add a subject and upload a few past papers first.</p>
              ) : (
                <div className="mt-4 flex flex-col gap-2 sm:flex-row">
                  <select className="input sm:max-w-xs" value={qp.subject} onChange={(e) => setQp({ ...qp, subject: Number(e.target.value) })}>
                    {data.subjects.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                  </select>
                  <select className="input sm:max-w-[160px]" value={qp.exam} onChange={(e) => setQp({ ...qp, exam: e.target.value as ExamType })}>
                    {EXAM_TYPES.map((t) => <option key={t} value={t}>{EXAM_LABEL[t]}</option>)}
                  </select>
                  <button className="btn-primary" onClick={generate} disabled={generating}>{generating ? <Spinner /> : <Sparkles className="h-4 w-4" />} Generate</button>
                </div>
              )}
              {qp.subject !== "" && (
                <Link to={`/app/subjects/${qp.subject}/predictions?exam=${qp.exam}`} className="mt-3 inline-flex items-center gap-1 text-sm text-lav-600 hover:underline">
                  Or browse all ranked questions <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              )}
            </div>
          </section>

          {/* exams */}
          <section className="card p-5">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="flex items-center gap-2 font-semibold"><CalendarClock className="h-4 w-4 text-lav-500" /> Upcoming exams</h2>
              {data.subjects.length > 0 && <button className="btn-ghost btn-sm" onClick={() => setShowExam(!showExam)}><Plus className="h-3.5 w-3.5" /> Add</button>}
            </div>
            {showExam && (
              <form onSubmit={addExam} className="mb-3 space-y-2 rounded-xl bg-lav-50/60 p-3">
                <select className="input" value={examForm.subject_id} onChange={(e) => setExamForm({ ...examForm, subject_id: Number(e.target.value) })}>
                  {data.subjects.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
                <div className="flex gap-2">
                  <select className="input" value={examForm.exam_type} onChange={(e) => setExamForm({ ...examForm, exam_type: e.target.value })}>
                    {EXAM_TYPES.map((t) => <option key={t} value={t}>{EXAM_LABEL[t]}</option>)}
                  </select>
                  <input className="input" type="date" value={examForm.date} min={todayISO()} onChange={(e) => setExamForm({ ...examForm, date: e.target.value })} />
                </div>
                <button className="btn-primary btn-sm w-full">Add exam</button>
              </form>
            )}
            {data.exams.length === 0 ? (
              <p className="text-sm muted">No exams added yet. Add your CAT or semester dates to track the countdown.</p>
            ) : (
              <ul className="space-y-2">
                {data.exams.map((e) => (
                  <li key={e.id} className="group flex items-center gap-3 rounded-xl px-2 py-1.5 hover:bg-stone-50">
                    <div className={`grid h-11 w-11 shrink-0 place-items-center rounded-xl text-center ${e.days_left <= 7 ? "bg-amber-50 text-amber-700" : "bg-lav-50 text-lav-700"}`}>
                      <div className="font-display text-base font-semibold leading-none">{e.days_left}</div>
                      <div className="text-[9px] uppercase">days</div>
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium">{EXAM_LABEL[e.exam_type] || e.exam_type} · {e.subject}</div>
                      <div className="text-xs muted">{new Date(e.date).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })}</div>
                    </div>
                    <button className="btn-ghost btn-sm opacity-0 group-hover:opacity-100" onClick={async () => { if (await confirm("Remove this exam?", "Remove")) { await api.deleteExam(e.id); reload(true); } }}>
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* subjects */}
          <section className="lg:col-span-2">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="font-semibold">Recently analysed subjects</h2>
              <Link to="/app/subjects" className="text-sm text-lav-600 hover:underline">All subjects</Link>
            </div>
            {data.subjects.length === 0 ? (
              <Empty icon={<BookOpen className="h-5 w-5" />} title="No subjects yet" action={<Link to="/app/subjects" className="btn-primary">Create a subject</Link>}>
                Create a subject, then upload its previous CAT and semester papers.
              </Empty>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2">
                {data.subjects.slice(0, 4).map((s) => (
                  <Link key={s.id} to={`/app/subjects/${s.id}`} className="card group p-4 transition hover:-translate-y-0.5 hover:shadow-lift">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="text-xs muted">{s.code || "—"}</div>
                        <div className="truncate font-medium">{s.name}</div>
                      </div>
                      {s.is_demo && <span className="chip shrink-0 bg-amber-50 text-amber-700">Sample</span>}
                    </div>
                    <div className="mt-3 flex items-center justify-between text-xs muted">
                      <span>{s.papers} papers · updated {relTime(s.updated_at)}</span>
                      <span>{s.progress}%</span>
                    </div>
                    <div className="mt-1.5"><Bar value={s.progress} /></div>
                  </Link>
                ))}
              </div>
            )}
          </section>

          {/* progress */}
          <section className="card p-5">
            <h2 className="mb-3 font-semibold">Today's plan</h2>
            {data.plan_today.length === 0 ? (
              <p className="text-sm muted">Nothing scheduled today. <Link to="/app/planner" className="text-lav-600 hover:underline">Build a study plan</Link></p>
            ) : (
              <ul className="space-y-2">
                {data.plan_today.map((p) => (
                  <li key={p.id} className="flex items-start gap-2 text-sm">
                    <input type="checkbox" className="mt-1 accent-lav-500" checked={p.done} onChange={async () => { await api.patchPlan(p.id, { done: !p.done }); reload(true); }} />
                    <span className={p.done ? "line-through muted" : ""}>{p.title}</span>
                  </li>
                ))}
              </ul>
            )}
            <div className="mt-5 border-t border-line pt-4">
              <div className="flex items-center justify-between text-sm">
                <span className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-600" /> Saved questions prepared</span>
                <span className="font-medium">{data.saved.completed}/{data.saved.total}</span>
              </div>
              <div className="mt-2"><Bar value={data.saved.total ? (100 * data.saved.completed) / data.saved.total : 0} className="bg-emerald-500" /></div>
            </div>
          </section>

          {/* uploads */}
          <section className="card p-5 lg:col-span-2">
            <h2 className="mb-3 font-semibold">Recent uploads</h2>
            {data.recent_documents.length === 0 ? <p className="text-sm muted">No uploads yet.</p> : (
              <ul className="divide-y divide-line">
                {data.recent_documents.map((d) => (
                  <li key={d.id} className="flex items-center gap-3 py-2.5">
                    <FileText className="h-4 w-4 shrink-0 text-ink-mute" />
                    <Link to={`/app/subjects/${d.subject_id}?tab=documents`} className="min-w-0 flex-1">
                      <div className="truncate text-sm">{d.filename}</div>
                      <div className="truncate text-xs muted">{d.subject} · {d.kind === "question_paper" ? `${EXAM_LABEL[d.exam_type]} ${d.academic_year}` : KIND_LABEL[d.kind]}</div>
                    </Link>
                    <span className={`chip shrink-0 ${DOC_STATUS_STYLE[d.status] || ""}`}>{DOC_STATUS_LABEL[d.status] || d.status}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="card p-5">
            <h2 className="mb-3 font-semibold">Recent predictions</h2>
            {data.recent_predictions.length === 0 ? <p className="text-sm muted">Generated papers will show up here.</p> : (
              <ul className="space-y-1">
                {data.recent_predictions.map((p) => (
                  <li key={p.id}>
                    <Link to={`/app/papers/${p.id}`} className="block rounded-lg px-2 py-1.5 hover:bg-stone-50">
                      <div className="truncate text-sm">{p.title}</div>
                      <div className="text-xs muted">{p.subject} · {relTime(p.created_at)}</div>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
