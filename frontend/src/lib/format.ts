import type { Evidence, ExamType, Priority, TopicStatus } from "../api";

export const EXAM_LABEL: Record<string, string> = { CAT1: "CAT 1", CAT2: "CAT 2", SEMESTER: "Semester", NA: "—" };
export const EXAM_TYPES: ExamType[] = ["CAT1", "CAT2", "SEMESTER"];

export const PRIORITY_LABEL: Record<Priority, string> = {
  very_high: "Very high", high: "High", moderate: "Moderate", lower: "Lower",
};
export const PRIORITY_STYLE: Record<Priority, string> = {
  very_high: "bg-lav-100 text-lav-700 ring-1 ring-lav-200",
  high: "bg-sky2-50 text-sky2-600 ring-1 ring-sky2-100",
  moderate: "bg-slate-100 text-slate-600 ring-1 ring-slate-200",
  lower: "bg-stone-100 text-stone-500 ring-1 ring-stone-200",
};
export const PRIORITY_BAR: Record<Priority, string> = {
  very_high: "bg-lav-500", high: "bg-sky2-500", moderate: "bg-slate-400", lower: "bg-stone-300",
};
export const PRIORITY_HEX: Record<Priority, string> = {
  very_high: "#8b7cf6", high: "#5b86d9", moderate: "#94a3b8", lower: "#d6d3d1",
};

export const EVIDENCE_SHORT: Record<Evidence, string> = {
  exact_repeat: "Exact repeat",
  concept_repeat: "Repeated concept",
  previously_asked: "Asked once",
  question_bank: "Question bank",
  practice_new: "Generated practice",
  predicted_variation: "Generated variation",
};
export const EVIDENCE_STYLE: Record<Evidence, string> = {
  exact_repeat: "bg-emerald-50 text-emerald-700",
  concept_repeat: "bg-teal-50 text-teal-700",
  previously_asked: "bg-sky2-50 text-sky2-600",
  question_bank: "bg-amber-50 text-amber-700",
  practice_new: "bg-orange-50 text-orange-700",
  predicted_variation: "bg-orange-50 text-orange-700",
};

export const QTYPE_LABEL: Record<string, string> = {
  theory: "Theory", definition: "Definition", diagram: "Diagram", derivation: "Derivation",
  numerical: "Numerical", programming: "Programming", comparison: "Comparison",
};
export const QTYPES = Object.keys(QTYPE_LABEL);

export const STATUS_LABEL: Record<TopicStatus, string> = {
  not_started: "Not started", studying: "Studying", completed: "Completed", revision: "Needs revision",
};
export const STATUS_STYLE: Record<TopicStatus, string> = {
  not_started: "bg-stone-100 text-stone-500",
  studying: "bg-sky2-50 text-sky2-600",
  completed: "bg-emerald-50 text-emerald-700",
  revision: "bg-amber-50 text-amber-700",
};
export const STATUSES: TopicStatus[] = ["not_started", "studying", "completed", "revision"];

export const DOC_STATUS_STYLE: Record<string, string> = {
  done: "bg-emerald-50 text-emerald-700",
  needs_review: "bg-amber-50 text-amber-700",
  processing: "bg-sky2-50 text-sky2-600",
  pending: "bg-stone-100 text-stone-500",
  failed: "bg-rose-50 text-rose-700",
};
export const DOC_STATUS_LABEL: Record<string, string> = {
  done: "Analysed", needs_review: "Needs review", processing: "Processing", pending: "Waiting", failed: "Failed",
};
export const KIND_LABEL: Record<string, string> = {
  question_paper: "Question paper", syllabus: "Syllabus", question_bank: "Question bank",
};

export const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function relTime(iso: string): string {
  const d = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z");
  const s = (Date.now() - d.getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  if (s < 86400 * 30) return `${Math.floor(s / 86400)} d ago`;
  return d.toLocaleDateString();
}

export function pct(v: number | null | undefined): string {
  return v === null || v === undefined ? "—" : `${Math.round(v * 100)}%`;
}

export function todayISO(offsetDays = 0): string {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

export function fmtBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}
