import { BarChart3, BookText, ClipboardCheck, FileText, Gauge, LayoutGrid, ListChecks, Settings, Sparkles, Upload } from "lucide-react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { Notice, PageHeader, PageLoader, SampleBadge, Tabs } from "../components/ui";
import { EXAM_LABEL, EXAM_TYPES } from "../lib/format";
import { useAsync } from "../lib/hooks";
import AccuracyTab from "./workspace/Accuracy";
import AnalysisTab from "./workspace/Analysis";
import DocumentsTab from "./workspace/Documents";
import OverviewTab from "./workspace/Overview";
import QuestionsTab from "./workspace/Questions";
import ReviewTab from "./workspace/Review";
import SettingsTab from "./workspace/Settings";
import SyllabusTab from "./workspace/Syllabus";

type Tab = "overview" | "documents" | "questions" | "review" | "syllabus" | "analysis" | "predictions" | "accuracy" | "settings";

export default function Workspace() {
  const id = Number(useParams().id);
  const [params, setParams] = useSearchParams();
  const tab = (params.get("tab") as Tab) || "overview";
  const { data: subject, error, reload } = useAsync(() => api.subject(id), [id]);
  const { data: review, reload: reloadReview } = useAsync(() => api.review(id), [id]);
  const waiting = review ? review.unmapped.length + review.uncertain.length : 0;

  const setTab = (t: Tab) => setParams((p) => { p.set("tab", t); return p; }, { replace: true });

  if (error) return <Notice tone="warn">{error}</Notice>;
  if (!subject) return <PageLoader />;

  return (
    <div>
      <PageHeader
        eyebrow={<Link to="/app/subjects" className="hover:underline">Subjects</Link>}
        title={<span className="flex flex-wrap items-center gap-3">{subject.name}{subject.is_demo && <SampleBadge />}</span>}
        subtitle={`${subject.code || "No code"} · ${subject.department || "—"} · Regulation ${subject.regulation} · Semester ${subject.semester}`}
        actions={<>
          <Link to={`/app/upload?subject=${id}`} className="btn-outline"><Upload className="h-4 w-4" /> Upload</Link>
          <Link to={`/app/subjects/${id}/predictions?exam=SEMESTER`} className="btn-primary"><Sparkles className="h-4 w-4" /> Predictions</Link>
        </>}
      />
      <Tabs<Tab> value={tab} onChange={setTab} tabs={[
        { id: "overview", label: "Overview", icon: <LayoutGrid className="h-3.5 w-3.5" /> },
        { id: "documents", label: "Documents", icon: <FileText className="h-3.5 w-3.5" /> },
        { id: "questions", label: "Questions", icon: <ListChecks className="h-3.5 w-3.5" /> },
        { id: "review", label: waiting ? `Review · ${waiting}` : "Review", icon: <ClipboardCheck className="h-3.5 w-3.5" /> },
        { id: "syllabus", label: "Syllabus", icon: <BookText className="h-3.5 w-3.5" /> },
        { id: "analysis", label: "Analysis", icon: <BarChart3 className="h-3.5 w-3.5" /> },
        { id: "predictions", label: "Predictions", icon: <Sparkles className="h-3.5 w-3.5" /> },
        { id: "accuracy", label: "Accuracy", icon: <Gauge className="h-3.5 w-3.5" /> },
        { id: "settings", label: "Settings", icon: <Settings className="h-3.5 w-3.5" /> },
      ]} />
      {tab === "overview" && <OverviewTab subject={subject} onTab={setTab} />}
      {tab === "documents" && <DocumentsTab subject={subject} onChange={() => reload(true)} />}
      {tab === "questions" && <QuestionsTab subject={subject} />}
      {tab === "review" && <ReviewTab subject={subject} onChange={() => { reload(true); reloadReview(true); }} />}
      {tab === "syllabus" && <SyllabusTab subject={subject} onSaved={() => { reload(true); reloadReview(true); }} />}
      {tab === "analysis" && <AnalysisTab subject={subject} />}
      {tab === "predictions" && (
        <div className="grid gap-4 sm:grid-cols-3">
          {EXAM_TYPES.map((t) => (
            <Link key={t} to={`/app/subjects/${id}/predictions?exam=${t}`} className="card group p-6 transition hover:-translate-y-0.5 hover:shadow-lift">
              <Sparkles className="h-5 w-5 text-lav-500" />
              <div className="mt-3 text-lg font-semibold">{EXAM_LABEL[t]} predictions</div>
              <p className="mt-1 text-sm muted">
                {t === "SEMESTER" ? "2, 13 and 15-mark questions across all units." : `2 and 11-mark questions for units ${subject.exam_config[t].units.join(", ")}.`}
              </p>
              <div className="mt-4 text-sm text-lav-600 group-hover:underline">Open →</div>
            </Link>
          ))}
        </div>
      )}
      {tab === "accuracy" && <AccuracyTab subject={subject} onApplied={() => reload(true)} />}
      {tab === "settings" && <SettingsTab subject={subject} onSaved={() => reload(true)} />}
    </div>
  );
}
