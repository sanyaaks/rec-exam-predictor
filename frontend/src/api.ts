// Small typed client for the FastAPI backend. JWT lives in localStorage.

const TOKEN_KEY = "rec_token";
const USER_KEY = "rec_user";

export type ExamType = "CAT1" | "CAT2" | "SEMESTER";
export type Priority = "very_high" | "high" | "moderate" | "lower";
export type Evidence =
  | "exact_repeat"
  | "concept_repeat"
  | "previously_asked"
  | "question_bank"
  | "practice_new"
  | "predicted_variation";
export type TopicStatus = "not_started" | "studying" | "completed" | "revision";

export interface User { id: number; email: string; name: string; department: string; is_guest: boolean }

export interface Section {
  name: string; title: string; marks_each: number; count: number;
  choice: "none" | "either_or"; instruction?: string;
}
export interface ExamPattern { label: string; units: number[]; duration: string; sections: Section[]; ranker?: "auto" | "statistical"; confirmed?: boolean }
export interface ClassificationCfg { min_similarity: number; keyword_score: number; name_match_score: number }
export interface ExamConfig {
  units_count: number;
  mark_categories: number[];
  CAT1: ExamPattern; CAT2: ExamPattern; SEMESTER: ExamPattern;
  priority_thresholds: { very_high: number; high: number; moderate: number };
  classification?: ClassificationCfg;
}
export type Weights = Record<string, number>;

export type TopicMeta = Record<string, { keywords?: string[]; subtopics?: string[] }>;
export interface Unit { id?: number; number: number; title: string; topics: string[]; hours: number | null; topic_meta?: TopicMeta }

export interface Subject {
  id: number; name: string; code: string; department: string; regulation: string; semester: number;
  syllabus_version?: string; is_demo: boolean; created_at: string;
  documents?: number; questions?: number; topics?: number; topics_completed?: number;
  has_syllabus?: boolean; updated_at?: string;
}
export interface SubjectFull extends Subject { exam_config: ExamConfig; weights: Weights; units: Unit[]; weights_by_type: Record<ExamType, Weights> }

export interface Doc {
  id: number; subject_id: number; filename: string; mime: string; kind: string; exam_type: string;
  academic_year: string; exam_year: number | null; exam_month: number | null; units_covered: number[];
  status: string; extraction_method: string; notes: string; page_count: number; is_sample: boolean;
  question_count: number; created_at: string; has_file: boolean; raw_text?: string;
  faculty_id?: string; feedback_for_prediction_id?: number | null;
  evaluation?: Evaluation | null;
}

export interface Question {
  id: number; document_id: number; number: string; choice: string; sub: string; section: string;
  text: string; marks: number | null; category: number | null; qtype: string; unit: number | null;
  topic: string; subtopic?: string; topic_source?: string; topic_confidence: number; co: string; bloom: string; confidence: number;
  verified: boolean; excluded: boolean; exam_type: string; exam_year: number | null;
  academic_year: string; doc_kind: string; doc_name: string; is_sample: boolean;
}

export interface DuplicateGroup {
  size: number; papers: number; exact: boolean; unit: number | null; topic: string; questions: Question[];
}

export interface Appearance {
  question_id: number | null; text: string; paper_id: number; paper: string; exam_type: string;
  year: number | null; number: string; marks: number | null;
}

export interface PredItem {
  id: string; cluster_id: string; text: string; marks: number; unit: number | null; topic: string;
  qtype: string; score: number; wording?: "past" | "past_other_marks" | "generated"; factors: Record<string, number>; factor_labels: Record<string, string>;
  priority: Priority; priority_label: string; evidence: Evidence; evidence_label: string;
  frequency: { papers: number; total_papers: number; by_type: Record<string, number>; weighted_share: number };
  years: number[]; appearances: Appearance[]; reasons: string[]; prep: string; is_generated: boolean;
  variation: { text: string; label: string; generated_by: string } | null;
  topic_score?: number | null; question_score?: number; topic_rank?: number | null; topic_key?: string; ranker?: string;
}

export interface TopicRow {
  key: string; label: string; unit: number | null; topic: string; pseudo: boolean; score: number; stat_score: number;
  ml_rank_score?: number | null; rank: number; priority: Priority; factors: Record<string, number>;
  stats: { papers: number; total_papers: number; questions: number; by_type: Record<string, number>; years: number[]; last_year: number | null; concepts: number; variants: number };
  examples: string[]; reasons: string[]; bank_hits: number;
}
export interface RankerInfo { mode: string; used: "statistical" | "ml"; model_version: number | null; model_version_id?: number; reason: string; stale?: { new_papers?: number; removed_papers?: number } }

export interface Confidence { level: "good" | "moderate" | "low"; message: string; papers: number; same_type_papers: number }
export interface Engine { similarity: string; engine_version?: string; weights: Weights; weight_labels: Record<string, string>; disclaimer: string }

export interface PredictionsResponse {
  exam_type: ExamType; items: PredItem[]; confidence: Confidence;
  unit_stats: Record<string, { recent_questions: number; all_questions: number; expected_share: number; coverage_factor: number }>;
  units: number[]; configured_units: number[]; engine: Engine; counts: Partial<Record<Priority, number>>;
  topics: TopicRow[]; ranker: RankerInfo;
}

export interface PaperQuestion { number: number; unit: number | null; options: PredItem[] }
export interface PaperSection {
  name: string; title: string; instruction: string; marks_each: number; count: number;
  choice: string; total: number; questions: PaperQuestion[];
}
export interface Paper {
  exam_type: ExamType; label: string; duration: string; units: number[]; total_marks: number;
  sections: PaperSection[]; seed: number; confidence: Confidence;
  ranker?: string; ranker_info?: RankerInfo; topic_ranking?: TopicRow[];
}
export interface PaperResponse { id: number; title: string; created_at: string; paper: Paper; subject: Subject; engine: Engine }
export interface PaperSummary { id: number; title: string; exam_type: ExamType; created_at: string; total_marks: number; confidence: string; ranker?: string; evaluated?: boolean }

export interface Analysis {
  papers: { id: number; label: string; exam_type: string; year: number | null; questions: number }[];
  totals: { papers: number; questions: number; bank_questions: number; syllabus_topics: number; topics_asked: number; concepts: number; repeated_concepts: number };
  units: { unit: number; title: string; questions: number; CAT1: number; CAT2: number; SEMESTER: number }[];
  unassigned_unit: number;
  marks_by_type: Record<string, Record<string, number>>;
  qtypes: { qtype: string; count: number }[];
  by_year: { year: number; CAT1: number; CAT2: number; SEMESTER: number }[];
  top_topics: { label: string; topic: string; unit: number | null; papers: number; questions: number; cat: number; semester: number; example: string }[];
  unit_priority: { unit: number; score: number; priority: Priority }[];
  untested_topics: { unit: number; topic: string }[];
  confidence: Confidence;
}

export interface RankMetrics {
  "precision@5": number; "recall@5": number; "ndcg@5": number; "precision@10": number; "recall@10": number; "ndcg@10": number;
  "precision@R": number; "ndcg@R": number; exact_match_rate: number; semantic_topic_match_rate: number; unit_coverage: number | null;
  relevant_topics?: number; novel_topics?: number; folds?: number;
}
export type MatchLevel = "exact" | "semantic" | "topic" | "miss";
export interface MatchRow { text: string; marks: number | null; unit: number | null; topic?: string; match: MatchLevel; similarity: number; predicted: string | null }
export interface RankerSummary { frequency_baseline?: RankMetrics; statistical?: RankMetrics; ml?: RankMetrics }
export interface Fold {
  paper_id: number; paper: string; exam_type: string; year: number | null; train_papers: number; hidden_questions: number;
  relevant_topics: number; novel_topics: number;
  frequency_baseline: RankMetrics; statistical: RankMetrics; ml?: RankMetrics;
  rows?: MatchRow[]; top_topics?: { label: string; unit: number | null; score: number; asked: boolean }[]; missed_topics?: string[];
}
export interface Backtest {
  folds: Fold[]; summary: RankerSummary | null; by_exam_type: Partial<Record<ExamType, RankerSummary>>;
  enough_data: boolean; ml_backend: string | null; note: string; undated_papers?: string[];
}

export interface WeightRow {
  name: string; weights: Weights; objective: number; "precision@5": number; "recall@10": number; "ndcg@10": number;
  "ndcg@R": number; exact_match_rate: number; semantic_topic_match_rate: number; unit_coverage: number | null;
}
export interface WeightCompare { rows: WeightRow[]; best: string | null; folds?: number; enough_data: boolean; note: string; exam_type?: string | null }

export interface ReadinessCheck { key: string; label: string; status: "ok" | "warn" | "missing" | "info"; detail: string; action: string | null }
export interface Readiness { exam_type: ExamType; checks: ReadinessCheck[]; ready: boolean; summary: string }

export interface Suggestion { unit: number; topic: string; score: number }
export interface Review { unmapped: (Question & { suggestions: Suggestion[] })[]; uncertain: (Question & { ocr: boolean })[]; has_syllabus: boolean }
export interface DiscoveredTopic { label: string; keywords: string[]; unit: number | null; suggested_topic: Suggestion | null; question_ids: number[]; examples: string[] }
export interface Discovery { method: string; topics: DiscoveredTopic[]; unclustered: number[]; unclassified: number }

export interface Retrieved { id: number; text: string; paper: string | null; similarity: number }
export interface GeneratedQ {
  id: number; unit: number | null; topic: string; marks: number; text: string; kind: "variation" | "new_practice"; qtype: string;
  source: "llm" | "template"; model: string; prompt_version: string; created_at: string; is_generated: true; label: string;
  grounding: { based_on: number[]; retrieved: Retrieved[] };
}
export interface GenerateResult { questions: GeneratedQ[]; discarded: { text: string; reason: string }[]; source: string; retrieved: Retrieved[]; note: string }

export interface ModelGate {
  use_ml: boolean; reason?: string; backend?: string | null; origins?: number; positives?: number; dated_papers?: number;
  gate?: Record<string, number>; validation?: { paper: string; statistical_ndcg: number; ml_ndcg: number }[];
  statistical_ndcg?: number; ml_ndcg?: number;
}
export interface ModelVersion { id: number; version: number; kind: string; status: "active" | "rejected" | "archived" | "candidate"; engine_version: string; gate: ModelGate; train_papers: number; n_rows: number; created_at: string }
export interface ModelsResp { models: ModelVersion[]; active: ModelVersion | null; staleness: { new_papers?: number; removed_papers?: number }; ml_backend: string | null; gate: Record<string, number> }

export interface EvalMetrics extends Partial<RankMetrics> { counts?: Record<MatchLevel, number>; rows?: MatchRow[]; predicted_questions?: number; actual_questions?: number }
export interface Evaluation { id: number; prediction_id: number; document_id: number; document: string; forward: boolean; metrics: EvalMetrics; created_at: string; note: string }

export interface EngineInfo { version: string; embeddings: { backend: string; sbert: boolean; model: string | null; mode: string }; similarity: string; ml_backend: string | null; ml_gate: Record<string, number> }

export interface Prepared {
  question: string; marks: number; unit: number | null; topic: string; keywords: string[];
  outline: { heading: string; points: string[] }[]; length_guide: string; diagram_expected: boolean;
  related_questions: string[]; mode: "ai" | "rule_based"; answer_markdown: string | null; disclaimer: string;
}

export interface Saved {
  id: number; subject_id: number; subject: string; text: string; marks: number | null; unit: number | null;
  topic: string; evidence: string; priority: string; status: TopicStatus; note: string; created_at: string;
}
export interface Progress {
  units: { unit: number; title: string; topics: { topic: string; status: TopicStatus }[]; completed: number; total: number }[];
  completed: number; total: number; percent: number;
}
export interface Exam { id: number; subject_id: number; subject: string; exam_type: string; date: string; title: string; days_left: number }
export interface PlanItem { id: number; date: string; title: string; subject_id: number | null; subject: string; unit: number | null; minutes: number; done: boolean }

export interface Dashboard {
  subjects: { id: number; name: string; code: string; is_demo: boolean; papers: number; progress: number; updated_at: string }[];
  recent_documents: { id: number; subject_id: number; subject: string; filename: string; exam_type: string; kind: string; status: string; academic_year: string; created_at: string }[];
  exams: Exam[];
  plan_today: PlanItem[];
  recent_predictions: { id: number; title: string; subject: string; subject_id: number; exam_type: string; created_at: string }[];
  saved: { total: number; completed: number };
}

export interface Meta {
  llm_enabled: boolean; ocr: string | null; similarity: string; default_exam_config: ExamConfig;
  default_weights: Weights; weight_labels: Record<string, string>; limitations: string[];
  engine?: EngineInfo;
}

// ------------------------------------------------------------------ core
export const auth = {
  token: () => localStorage.getItem(TOKEN_KEY),
  user: (): User | null => {
    try { return JSON.parse(localStorage.getItem(USER_KEY) || "null"); } catch { return null; }
  },
  set(token: string, user: User) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  },
  clear() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  },
};

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) { super(message); this.status = status; }
}

function onUnauthorized() {
  auth.clear();
  if (!location.pathname.startsWith("/login")) location.href = "/login?expired=1";
}

async function errorMessage(res: Response): Promise<string> {
  try {
    const j = await res.json();
    if (typeof j.detail === "string") return j.detail;
    if (Array.isArray(j.detail)) return j.detail.map((d: { msg: string }) => d.msg).join("; ");
  } catch { /* ignore */ }
  return `Request failed (${res.status})`;
}

export async function request<T>(path: string, opts: { method?: string; body?: unknown; raw?: boolean } = {}): Promise<T> {
  const headers: Record<string, string> = {};
  const t = auth.token();
  if (t) headers.Authorization = `Bearer ${t}`;
  let body: BodyInit | undefined;
  if (opts.body instanceof FormData) body = opts.body;
  else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  const res = await fetch(path, { method: opts.method || "GET", headers, body });
  if (res.status === 401 && t) {
    onUnauthorized();
    throw new ApiError(401, "Session expired");
  }
  if (!res.ok) throw new ApiError(res.status, await errorMessage(res));
  if (opts.raw) return res as unknown as T;
  return res.json() as Promise<T>;
}

export async function downloadFile(path: string, fallbackName: string) {
  const res = await request<Response>(path, { raw: true });
  const blob = await res.blob();
  const cd = res.headers.get("Content-Disposition") || "";
  const m = cd.match(/filename="?([^";]+)"?/);
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = m ? m[1] : fallbackName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

export function uploadWithProgress(path: string, form: FormData, onProgress: (pct: number) => void): Promise<Doc[]> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", path);
    const t = auth.token();
    if (t) xhr.setRequestHeader("Authorization", `Bearer ${t}`);
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100)); };
    xhr.onload = () => {
      if (xhr.status === 401) { onUnauthorized(); return reject(new ApiError(401, "Session expired")); }
      let data: unknown = null;
      try { data = JSON.parse(xhr.responseText); } catch { /* ignore */ }
      if (xhr.status >= 200 && xhr.status < 300) resolve(data as Doc[]);
      else reject(new ApiError(xhr.status, (data as { detail?: string })?.detail || `Upload failed (${xhr.status})`));
    };
    xhr.onerror = () => reject(new ApiError(0, "Network error during upload"));
    xhr.send(form);
  });
}

// ------------------------------------------------------------------ endpoints
type AuthResp = { token: string; user: User };
export const api = {
  register: (b: { email: string; password: string; name: string; department: string }) => request<AuthResp>("/api/auth/register", { method: "POST", body: b }),
  login: (b: { email: string; password: string }) => request<AuthResp>("/api/auth/login", { method: "POST", body: b }),
  guest: () => request<AuthResp>("/api/auth/guest", { method: "POST" }),
  me: () => request<User>("/api/auth/me"),
  meta: () => request<Meta>("/api/meta"),
  dashboard: () => request<Dashboard>("/api/dashboard"),

  subjects: () => request<Subject[]>("/api/subjects"),
  createSubject: (b: { name: string; code: string; department: string; regulation: string; semester: number }) =>
    request<SubjectFull>("/api/subjects", { method: "POST", body: b }),
  subject: (id: number) => request<SubjectFull>(`/api/subjects/${id}`),
  patchSubject: (id: number, b: Partial<{ name: string; code: string; department: string; regulation: string; semester: number; syllabus_version: string; exam_config: ExamConfig; weights: Weights | Record<string, Weights> }>) =>
    request<SubjectFull>(`/api/subjects/${id}`, { method: "PATCH", body: b }),
  deleteSubject: (id: number) => request(`/api/subjects/${id}`, { method: "DELETE" }),
  putSyllabus: (id: number, units: Unit[], syllabus_version?: string) => request<SubjectFull>(`/api/subjects/${id}/syllabus`, { method: "PUT", body: { units, syllabus_version } }),
  parseSyllabus: (id: number, text: string) => request<{ units: Unit[] }>(`/api/subjects/${id}/syllabus/parse`, { method: "POST", body: { text } }),

  documents: (id: number) => request<Doc[]>(`/api/subjects/${id}/documents`),
  document: (id: number) => request<Doc & { questions: Question[] }>(`/api/documents/${id}`),
  patchDocument: (id: number, b: Partial<Doc>) => request<Doc>(`/api/documents/${id}`, { method: "PATCH", body: b }),
  reprocess: (id: number) => request<Doc>(`/api/documents/${id}/reprocess`, { method: "POST" }),
  deleteDocument: (id: number) => request(`/api/documents/${id}`, { method: "DELETE" }),
  pasteDocument: (sid: number, b: { text: string; title: string; kind: string; exam_type: string; academic_year: string; exam_year: number | null; exam_month: number | null; units_covered: number[]; faculty_id?: string; feedback_for_prediction_id?: number | null }) =>
    request<Doc>(`/api/subjects/${sid}/documents/text`, { method: "POST", body: b }),

  questions: (sid: number, params: Record<string, string | number | boolean | undefined>) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== "" && v !== false) qs.set(k, String(v)); });
    return request<Question[]>(`/api/subjects/${sid}/questions?${qs}`);
  },
  addQuestion: (docId: number, b: Partial<Question> & { text: string }) => request<Question>(`/api/documents/${docId}/questions`, { method: "POST", body: b }),
  patchQuestion: (id: number, b: Partial<Question>) => request<Question>(`/api/questions/${id}`, { method: "PATCH", body: b }),
  deleteQuestion: (id: number) => request(`/api/questions/${id}`, { method: "DELETE" }),
  duplicates: (sid: number) => request<DuplicateGroup[]>(`/api/subjects/${sid}/duplicates`),

  analysis: (sid: number) => request<Analysis>(`/api/subjects/${sid}/analysis`),
  predictions: (sid: number, exam: ExamType, units?: number[] | null) =>
    request<PredictionsResponse>(`/api/subjects/${sid}/predictions?exam_type=${exam}${units && units.length ? `&units=${units.join(",")}` : ""}`),
  generatePaper: (sid: number, exam_type: ExamType, seed = 0, units?: number[] | null) =>
    request<PaperResponse>(`/api/subjects/${sid}/papers`, { method: "POST", body: { exam_type, seed, units: units && units.length ? units : null } }),
  readiness: (sid: number, exam: ExamType) => request<Readiness>(`/api/subjects/${sid}/readiness?exam_type=${exam}`),
  review: (sid: number) => request<Review>(`/api/subjects/${sid}/review`),
  discover: (sid: number, method = "auto") => request<Discovery>(`/api/subjects/${sid}/discover?method=${method}`, { method: "POST" }),
  applyDiscovery: (sid: number, b: { question_ids: number[]; unit: number; topic: string; create_topic: boolean; keywords: string[] }) =>
    request<{ ok: boolean; assigned: number }>(`/api/subjects/${sid}/discover/apply`, { method: "POST", body: b }),
  generateQuestions: (sid: number, b: { topic: string; unit: number | null; marks: number; count: number }) =>
    request<GenerateResult>(`/api/subjects/${sid}/generate`, { method: "POST", body: b }),
  generated: (sid: number, topic?: string) => request<GeneratedQ[]>(`/api/subjects/${sid}/generated${topic ? `?topic=${encodeURIComponent(topic)}` : ""}`),
  deleteGenerated: (id: number) => request(`/api/generated/${id}`, { method: "DELETE" }),
  models: (sid: number) => request<ModelsResp>(`/api/subjects/${sid}/models`),
  trainModel: (sid: number) => request<{ model: ModelVersion; message: string }>(`/api/subjects/${sid}/models/train`, { method: "POST" }),
  activateModel: (id: number) => request<ModelVersion>(`/api/models/${id}/activate`, { method: "POST" }),
  archiveModel: (id: number) => request<ModelVersion>(`/api/models/${id}/archive`, { method: "POST" }),
  evaluatePaper: (pid: number, document_id: number) => request<Evaluation>(`/api/papers/${pid}/evaluate`, { method: "POST", body: { document_id } }),
  evaluations: (pid: number) => request<Evaluation[]>(`/api/papers/${pid}/evaluations`),
  papers: (sid: number) => request<PaperSummary[]>(`/api/subjects/${sid}/papers`),
  paper: (id: number) => request<PaperResponse>(`/api/papers/${id}`),
  deletePaper: (id: number) => request(`/api/papers/${id}`, { method: "DELETE" }),
  backtest: (sid: number) => request<Backtest>(`/api/subjects/${sid}/backtest`),
  compareWeights: (sid: number, exam?: ExamType | null) => request<WeightCompare>(`/api/subjects/${sid}/backtest/weights${exam ? `?exam_type=${exam}` : ""}`),
  prepare: (sid: number, b: { text: string; marks: number; qtype: string; topic: string; unit: number | null; related: string[] }) =>
    request<Prepared>(`/api/subjects/${sid}/prepare`, { method: "POST", body: b }),

  saved: (subject_id?: number) => request<Saved[]>(`/api/saved${subject_id ? `?subject_id=${subject_id}` : ""}`),
  save: (b: { subject_id: number; text: string; marks: number | null; unit: number | null; topic: string; evidence: string; priority: string }) =>
    request<Saved>("/api/saved", { method: "POST", body: b }),
  patchSaved: (id: number, b: { status?: TopicStatus; note?: string }) => request<Saved>(`/api/saved/${id}`, { method: "PATCH", body: b }),
  deleteSaved: (id: number) => request(`/api/saved/${id}`, { method: "DELETE" }),

  progress: (sid: number) => request<Progress>(`/api/subjects/${sid}/progress`),
  setProgress: (sid: number, b: { unit: number; topic: string; status: TopicStatus }) => request(`/api/subjects/${sid}/progress`, { method: "PUT", body: b }),

  exams: () => request<Exam[]>("/api/exams"),
  addExam: (b: { subject_id: number; exam_type: string; date: string; title: string }) => request<Exam>("/api/exams", { method: "POST", body: b }),
  deleteExam: (id: number) => request(`/api/exams/${id}`, { method: "DELETE" }),

  plan: () => request<PlanItem[]>("/api/plan"),
  addPlan: (b: { date: string; title: string; subject_id: number | null; unit: number | null; minutes: number }) => request<PlanItem>("/api/plan", { method: "POST", body: b }),
  patchPlan: (id: number, b: Partial<PlanItem>) => request<PlanItem>(`/api/plan/${id}`, { method: "PATCH", body: b }),
  deletePlan: (id: number) => request(`/api/plan/${id}`, { method: "DELETE" }),
  autoPlan: (exam_id: number, minutes_per_day: number) => request<PlanItem[]>("/api/plan/auto", { method: "POST", body: { exam_id, minutes_per_day } }),
};
