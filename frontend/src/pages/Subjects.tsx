import { BookOpen, FileText, ListChecks, Plus } from "lucide-react";
import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, auth, SubjectFull } from "../api";
import { Bar, Empty, errMsg, Modal, PageHeader, SampleBadge, Skeleton, Spinner, useToast } from "../components/ui";
import { relTime } from "../lib/format";
import { useAsync } from "../lib/hooks";

export function NewSubjectForm({ onCreated, compact }: { onCreated: (s: SubjectFull) => void; compact?: boolean }) {
  const { toast } = useToast();
  const [f, setF] = useState({ name: "", code: "", department: auth.user()?.department || "CSE", regulation: "2023", semester: 5 });
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!f.name.trim()) return;
    setBusy(true);
    try {
      const s = await api.createSubject(f);
      toast("Subject created");
      onCreated(s);
    } catch (err) {
      toast(errMsg(err), "error");
    } finally {
      setBusy(false);
    }
  };
  return (
    <form onSubmit={submit} className="space-y-3">
      <div>
        <label className="label">Subject name</label>
        <input className="input" required value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="e.g. Computer Networks" />
      </div>
      <div className={`grid gap-3 ${compact ? "grid-cols-2" : "grid-cols-2"}`}>
        <div>
          <label className="label">Subject code</label>
          <input className="input" value={f.code} onChange={(e) => setF({ ...f, code: e.target.value })} placeholder="e.g. CS23501" />
        </div>
        <div>
          <label className="label">Department</label>
          <input className="input" value={f.department} onChange={(e) => setF({ ...f, department: e.target.value })} />
        </div>
        <div>
          <label className="label">Regulation</label>
          <select className="input" value={f.regulation} onChange={(e) => setF({ ...f, regulation: e.target.value })}>
            <option value="2023">2023</option><option value="2021">2021</option><option value="other">Other</option>
          </select>
        </div>
        <div>
          <label className="label">Semester</label>
          <select className="input" value={f.semester} onChange={(e) => setF({ ...f, semester: Number(e.target.value) })}>
            {[1, 2, 3, 4, 5, 6, 7, 8].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>
      </div>
      <button className="btn-primary w-full" disabled={busy}>{busy && <Spinner />} Create subject</button>
    </form>
  );
}

export default function SubjectsPage() {
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const { data, loading } = useAsync(() => api.subjects(), []);

  return (
    <div>
      <PageHeader title="Subjects" subtitle="Each subject keeps its own papers, syllabus, exam pattern and predictions."
        actions={<button className="btn-primary" onClick={() => setOpen(true)}><Plus className="h-4 w-4" /> New subject</button>} />
      {loading && !data ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-40" />)}</div>
      ) : !data?.length ? (
        <Empty icon={<BookOpen className="h-5 w-5" />} title="No subjects yet" action={<button className="btn-primary" onClick={() => setOpen(true)}>Create your first subject</button>}>
          Start with the subject you have an exam in next.
        </Empty>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.map((s) => {
            const prog = s.topics ? Math.round((100 * (s.topics_completed || 0)) / s.topics) : 0;
            return (
              <Link key={s.id} to={`/app/subjects/${s.id}`} className="card flex flex-col p-5 transition hover:-translate-y-0.5 hover:shadow-lift">
                <div className="text-xs muted">{s.code || "No code"} · Sem {s.semester} · R{s.regulation}</div>
                <div className="mt-0.5 text-lg font-semibold leading-snug">{s.name}</div>
                {s.is_demo && <div className="mt-2"><SampleBadge /></div>}
                <div className="mt-4 flex gap-4 text-xs muted">
                  <span className="flex items-center gap-1"><FileText className="h-3.5 w-3.5" /> {s.documents} papers</span>
                  <span className="flex items-center gap-1"><ListChecks className="h-3.5 w-3.5" /> {s.questions} questions</span>
                </div>
                {!s.has_syllabus && <div className="mt-2 text-xs text-amber-700">No syllabus yet — add it for better unit mapping</div>}
                <div className="mt-auto pt-4">
                  <div className="mb-1 flex justify-between text-xs muted"><span>Topics completed</span><span>{prog}%</span></div>
                  <Bar value={prog} />
                  <div className="mt-2 text-[11px] muted">Updated {relTime(s.updated_at || s.created_at)}</div>
                </div>
              </Link>
            );
          })}
        </div>
      )}
      <Modal open={open} onClose={() => setOpen(false)} title="New subject">
        <NewSubjectForm onCreated={(s) => nav(`/app/subjects/${s.id}`)} />
      </Modal>
    </div>
  );
}
