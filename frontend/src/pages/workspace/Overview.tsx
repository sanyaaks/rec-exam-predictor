import { ArrowRight, BookText, CheckCircle2, Circle, Database, FileText, ListChecks, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { api, downloadFile, SubjectFull } from "../../api";
import { errMsg, Notice, Stat, useToast } from "../../components/ui";
import { EXAM_LABEL } from "../../lib/format";
import { useAsync } from "../../lib/hooks";

type TabId = "documents" | "questions" | "syllabus" | "analysis" | "accuracy" | "settings";

export default function OverviewTab({ subject, onTab }: { subject: SubjectFull; onTab: (t: TabId) => void }) {
  const { toast } = useToast();
  const { data: docs } = useAsync(() => api.documents(subject.id), [subject.id]);
  const { data: papers } = useAsync(() => api.papers(subject.id), [subject.id]);
  const qp = docs?.filter((d) => d.kind === "question_paper") || [];
  const review = docs?.filter((d) => d.status === "needs_review" || d.status === "failed") || [];
  const hasType = (t: string) => qp.some((d) => d.exam_type === t);

  const steps = [
    { done: subject.units.length > 0, label: "Add the syllabus (units & topics)", tab: "syllabus" as TabId },
    { done: hasType("CAT1") || hasType("CAT2"), label: "Upload previous CAT papers", link: `/app/upload?subject=${subject.id}` },
    { done: hasType("SEMESTER"), label: "Upload previous semester papers", link: `/app/upload?subject=${subject.id}` },
    { done: review.length === 0 && qp.length > 0, label: "Review extracted questions", tab: "questions" as TabId },
    { done: (papers?.length || 0) > 0, label: "Generate a predicted paper", link: `/app/subjects/${subject.id}/predictions?exam=SEMESTER` },
  ];

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Question papers" value={qp.length} icon={<FileText className="h-4 w-4" />} />
        <Stat label="Extracted questions" value={subject.questions ?? "—"} icon={<ListChecks className="h-4 w-4" />} />
        <Stat label="Syllabus topics" value={subject.topics ?? 0} hint={subject.units.length ? `${subject.units.length} units` : "No syllabus yet"} icon={<BookText className="h-4 w-4" />} />
        <Stat label="Predictions made" value={papers?.length ?? "—"} icon={<Sparkles className="h-4 w-4" />} />
      </div>

      <div className="card flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
        <Database className="h-5 w-5 shrink-0 text-lav-500" />
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium">Examination dataset</div>
          <div className="text-xs muted">One row per question: subject, regulation, exam type and year, faculty, question text (normalised), marks, type, unit, topic, subtopic, syllabus version and how many earlier papers asked it.</div>
        </div>
        <button className="btn-outline btn-sm shrink-0" onClick={() => downloadFile(`/api/subjects/${subject.id}/dataset?format=csv`, "dataset.csv").catch((e) => toast(errMsg(e), "error"))}>Export dataset (CSV)</button>
      </div>

      {review.length > 0 && (
        <Notice tone="warn">
          {review.length} document{review.length > 1 ? "s" : ""} need a quick check — some questions may have been extracted imperfectly.{" "}
          <button className="underline" onClick={() => onTab("questions")}>Review questions</button>
        </Notice>
      )}

      <div className="grid gap-5 lg:grid-cols-2">
        <div className="card p-5">
          <h3 className="mb-3 font-semibold">Getting to a good prediction</h3>
          <ul className="space-y-2.5">
            {steps.map((s) => (
              <li key={s.label} className="flex items-center gap-3 text-sm">
                {s.done ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : <Circle className="h-4 w-4 text-stone-300" />}
                <span className={s.done ? "muted line-through" : ""}>{s.label}</span>
                {!s.done && (s.link
                  ? <Link to={s.link} className="ml-auto text-xs text-lav-600 hover:underline">Do it</Link>
                  : <button onClick={() => s.tab && onTab(s.tab)} className="ml-auto text-xs text-lav-600 hover:underline">Do it</button>)}
              </li>
            ))}
          </ul>
          <p className="mt-4 text-xs muted">More past papers = more reliable patterns. Aim for at least 3 papers of the exam type you're preparing for.</p>
        </div>

        <div className="card p-5">
          <h3 className="mb-3 font-semibold">Exam patterns for this subject</h3>
          <div className="space-y-3">
            {(["CAT1", "CAT2", "SEMESTER"] as const).map((t) => {
              const p = subject.exam_config[t];
              return (
                <div key={t} className="rounded-xl bg-stone-50 px-3 py-2.5">
                  <div className="flex items-center justify-between text-sm font-medium">
                    {EXAM_LABEL[t]}<span className="text-xs font-normal muted">Units {p.units.join(", ")} · {p.duration}</span>
                  </div>
                  <div className="mt-1 text-xs muted">
                    {p.sections.map((s) => `${s.title}: ${s.count} × ${s.marks_each}${s.choice === "either_or" ? " (either/or)" : ""}`).join(" · ")}
                  </div>
                </div>
              );
            })}
          </div>
          <button className="mt-3 inline-flex items-center gap-1 text-sm text-lav-600 hover:underline" onClick={() => onTab("settings")}>Edit pattern <ArrowRight className="h-3.5 w-3.5" /></button>
        </div>
      </div>

      {papers && papers.length > 0 && (
        <div className="card p-5">
          <h3 className="mb-3 font-semibold">Previous predictions</h3>
          <ul className="divide-y divide-line">
            {papers.slice(0, 6).map((p) => (
              <li key={p.id}><Link to={`/app/papers/${p.id}`} className="flex items-center justify-between py-2 text-sm hover:text-lav-700">
                <span>{p.title}</span><span className="text-xs muted">{new Date(p.created_at + "Z").toLocaleString()}</span>
              </Link></li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
