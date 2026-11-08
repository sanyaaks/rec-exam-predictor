import { CheckCircle2, ClipboardPaste, FileImage, FileText, FileType, Plus, Target, UploadCloud, X } from "lucide-react";
import { DragEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, Doc, Evaluation, uploadWithProgress } from "../api";
import { Bar, errMsg, Modal, Notice, PageHeader, Spinner, useToast } from "../components/ui";
import { DOC_STATUS_LABEL, DOC_STATUS_STYLE, EXAM_LABEL, fmtBytes, KIND_LABEL, pct } from "../lib/format";
import { useAsync, useMeta } from "../lib/hooks";
import { DocMetaFields } from "./workspace/Documents";
import { NewSubjectForm } from "./Subjects";

const ACCEPT = [".pdf", ".docx", ".jpg", ".jpeg", ".png"];

interface Pending { key: string; file: File; preview?: string; meta: Partial<Doc> }

function guessMeta(name: string): Partial<Doc> {
  const n = name.toLowerCase();
  const kind = /syllab/.test(n) ? "syllabus" : /bank|important|imp\b/.test(n) ? "question_bank" : "question_paper";
  const exam_type = /cat\s*[-_]?\s*(1|i)\b|cat1|cat-1/.test(n) ? "CAT1" : /cat\s*[-_]?\s*(2|ii)\b|cat2|cat-2/.test(n) ? "CAT2" : "SEMESTER";
  const y = n.match(/20\d\d/);
  const months: Record<string, number> = { jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6, jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12 };
  const mk = Object.keys(months).find((m) => n.includes(m));
  return { kind, exam_type, exam_year: y ? Number(y[0]) : null, exam_month: mk ? months[mk] : null, academic_year: "", units_covered: [] };
}

function FileIcon({ f }: { f: File }) {
  if (f.type.startsWith("image/")) return <FileImage className="h-5 w-5" />;
  if (f.name.toLowerCase().endsWith(".docx")) return <FileType className="h-5 w-5" />;
  return <FileText className="h-5 w-5" />;
}

export function EvaluationCard({ ev, compact }: { ev: Evaluation; compact?: boolean }) {
  const m = ev.metrics;
  const tiles: [string, string][] = [
    ["Exact question match", pct(m.exact_match_rate)],
    ["Semantic / topic match", pct(m.semantic_topic_match_rate)],
    ["Unit coverage", pct(m.unit_coverage ?? null)],
    ["Precision@10 (topics)", pct(m["precision@10"])],
    ["NDCG@R (topics)", typeof m["ndcg@R"] === "number" ? m["ndcg@R"].toFixed(2) : "—"],
  ];
  return (
    <div className="card border-lav-200 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Target className="h-4 w-4 text-lav-500" />
        <h3 className="font-semibold">How did the prediction do?</h3>
        <span className={`chip ${ev.forward ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>{ev.forward ? "Forward test" : "Retrospective"}</span>
        {!compact && <Link to={`/app/papers/${ev.prediction_id}`} className="ml-auto text-sm text-lav-600 hover:underline">Open prediction →</Link>}
      </div>
      <p className="mt-1 text-xs muted">{ev.document} · {m.actual_questions} questions in the paper vs {m.predicted_questions} predicted. {ev.note}</p>
      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-5">
        {tiles.map(([k, v]) => <div key={k} className="rounded-xl bg-stone-50 px-3 py-2"><div className="text-[11px] muted">{k}</div><div className="font-display text-lg font-semibold">{v}</div></div>)}
      </div>
      {m.counts && <p className="mt-2 text-xs muted">Exact {m.counts.exact} · same concept {m.counts.semantic} · same topic {m.counts.topic} · missed {m.counts.miss}</p>}
    </div>
  );
}

export default function UploadPage() {
  const [params] = useSearchParams();
  const { toast } = useToast();
  const meta = useMeta();
  const { data: subjects, reload: reloadSubjects } = useAsync(() => api.subjects(), []);
  const [subjectId, setSubjectId] = useState<number | "">(params.get("subject") ? Number(params.get("subject")) : "");
  const [files, setFiles] = useState<Pending[]>([]);
  const [drag, setDrag] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [results, setResults] = useState<Doc[] | null>(null);
  const [newSubject, setNewSubject] = useState(false);
  const [paste, setPaste] = useState<{ text: string; title: string; meta: Partial<Doc>; busy: boolean } | null>(null);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => { if (subjects?.length && subjectId === "") setSubjectId(subjects[0].id); }, [subjects]); // eslint-disable-line
  useEffect(() => () => files.forEach((f) => f.preview && URL.revokeObjectURL(f.preview)), []); // eslint-disable-line

  const subject = useMemo(() => subjects?.find((s) => s.id === subjectId), [subjects, subjectId]);
  const { data: subjectFull } = useAsync(() => (subjectId ? api.subject(Number(subjectId)) : Promise.resolve(null)), [subjectId]);
  const { data: predictions } = useAsync(() => (subjectId ? api.papers(Number(subjectId)) : Promise.resolve([])), [subjectId]);
  const unitsCount = Math.max(subjectFull?.units.length || 0, subjectFull?.exam_config.units_count || 5);
  const feedbackFor = params.get("feedback") ? Number(params.get("feedback")) : null;

  const add = (list: FileList | File[]) => {
    const arr = Array.from(list);
    const bad = arr.filter((f) => !ACCEPT.some((e) => f.name.toLowerCase().endsWith(e)));
    if (bad.length) toast(`Skipped ${bad.map((b) => b.name).join(", ")} — use PDF, DOCX, JPG or PNG`, "error");
    const ok = arr.filter((f) => !bad.includes(f));
    setResults(null);
    setFiles((cur) => [...cur, ...ok.map((file) => ({
      key: `${file.name}-${file.size}-${Math.random()}`, file,
      preview: file.type.startsWith("image/") ? URL.createObjectURL(file) : undefined,
      meta: { ...guessMeta(file.name), feedback_for_prediction_id: feedbackFor },
    }))]);
  };

  const onDrop = (e: DragEvent) => { e.preventDefault(); setDrag(false); if (e.dataTransfer.files.length) add(e.dataTransfer.files); };

  const upload = async () => {
    if (!subjectId || !files.length) return;
    const form = new FormData();
    files.forEach((f) => form.append("files", f.file));
    form.append("meta", JSON.stringify(files.map((f) => ({ ...f.meta, exam_type: f.meta.kind === "question_paper" ? f.meta.exam_type : "NA" }))));
    setProgress(0);
    try {
      const docs = await uploadWithProgress(`/api/subjects/${subjectId}/documents`, form, setProgress);
      setResults(docs);
      setFiles([]);
      toast(`${docs.length} document${docs.length > 1 ? "s" : ""} analysed`);
    } catch (e) {
      toast(errMsg(e), "error");
    } finally {
      setProgress(null);
    }
  };

  const submitPaste = async () => {
    if (!paste || !subjectId) return;
    setPaste({ ...paste, busy: true });
    try {
      const m = paste.meta;
      const d = await api.pasteDocument(Number(subjectId), {
        text: paste.text, title: paste.title || "Pasted paper", kind: m.kind || "question_paper",
        exam_type: m.kind === "question_paper" ? m.exam_type || "SEMESTER" : "NA", academic_year: m.academic_year || "",
        exam_year: m.exam_year ?? null, exam_month: m.exam_month ?? null, units_covered: m.units_covered || [],
        faculty_id: m.faculty_id || "", feedback_for_prediction_id: m.feedback_for_prediction_id ?? null,
      });
      setResults([d]);
      setPaste(null);
      toast("Text analysed");
    } catch (e) { toast(errMsg(e), "error"); setPaste({ ...paste, busy: false }); }
  };

  return (
    <div>
      <PageHeader title="Upload papers" subtitle="Previous CAT papers, semester papers, the syllabus and question banks. Add the exam and year so trends are accurate." />

      <div className="card mb-5 flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
        <label className="text-sm font-medium sm:w-24">Subject</label>
        <select className="input sm:max-w-md" value={subjectId} onChange={(e) => setSubjectId(Number(e.target.value))}>
          {!subjects?.length && <option value="">No subjects yet</option>}
          {subjects?.map((s) => <option key={s.id} value={s.id}>{s.name}{s.code ? ` (${s.code})` : ""}</option>)}
        </select>
        <button className="btn-ghost btn-sm" onClick={() => setNewSubject(true)}><Plus className="h-3.5 w-3.5" /> New subject</button>
      </div>

      {meta && !meta.ocr && <div className="mb-4"><Notice>Photos and scanned PDFs need an OCR engine, which isn't installed on this server. Digital PDFs and Word files work fully — for scans, use “Paste text instead”.</Notice></div>}

      <div onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={onDrop} onClick={() => input.current?.click()}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-3xl border-2 border-dashed px-6 py-12 text-center transition ${drag ? "border-lav-400 bg-lav-50" : "border-line bg-white hover:border-lav-200 hover:bg-lav-50/40"}`}>
        <div className="rounded-2xl bg-gradient-to-br from-lav-100 to-sky2-50 p-4 text-lav-600"><UploadCloud className="h-7 w-7" /></div>
        <div className="mt-4 font-display text-lg font-semibold">Drop question papers here</div>
        <div className="mt-1 text-sm muted">or click to browse · PDF, DOCX, JPG, PNG · multiple files at once</div>
        <input ref={input} type="file" multiple accept={ACCEPT.join(",")} className="hidden" onChange={(e) => { if (e.target.files) add(e.target.files); e.target.value = ""; }} />
      </div>
      <div className="mt-3 text-center">
        <button className="inline-flex items-center gap-1.5 text-sm text-lav-600 hover:underline" onClick={() => setPaste({ text: "", title: "", meta: { kind: "question_paper", exam_type: "SEMESTER", units_covered: [], feedback_for_prediction_id: feedbackFor }, busy: false })}>
          <ClipboardPaste className="h-4 w-4" /> Paste text instead (for scanned papers)
        </button>
      </div>

      {files.length > 0 && (
        <div className="mt-6 space-y-3">
          {files.map((p, i) => (
            <div key={p.key} className="card p-4">
              <div className="mb-3 flex items-center gap-3">
                {p.preview ? <img src={p.preview} alt="" className="h-12 w-12 rounded-lg object-cover ring-1 ring-line" /> : <div className="rounded-xl bg-lav-50 p-2.5 text-lav-600"><FileIcon f={p.file} /></div>}
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium">{p.file.name}</div>
                  <div className="text-xs muted">{fmtBytes(p.file.size)} · {p.file.name.split(".").pop()?.toUpperCase()}</div>
                </div>
                <button className="btn-ghost btn-sm" onClick={() => setFiles(files.filter((_, j) => j !== i))} disabled={progress !== null}><X className="h-4 w-4" /></button>
              </div>
              <DocMetaFields value={p.meta} unitsCount={unitsCount} predictions={predictions || []} onChange={(m) => setFiles(files.map((x, j) => (j === i ? { ...x, meta: m } : x)))} />
            </div>
          ))}
          <div className="card sticky bottom-3 flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
            <div className="flex-1">
              {progress !== null ? (
                <>
                  <div className="mb-1 text-sm">{progress < 100 ? `Uploading… ${progress}%` : "Reading papers and extracting questions…"}</div>
                  <Bar value={progress} />
                </>
              ) : <div className="text-sm muted">{files.length} file{files.length > 1 ? "s" : ""} ready{subject ? ` for ${subject.name}` : ""}</div>}
            </div>
            <button className="btn-primary" onClick={upload} disabled={!subjectId || progress !== null}>{progress !== null && <Spinner />} Upload & analyse</button>
          </div>
        </div>
      )}

      {results && (
        <div className="mt-6">
          <h2 className="mb-3 font-semibold">Extraction results</h2>
          <div className="space-y-2">
            {results.map((d) => (
              <div key={d.id} className="card flex flex-col gap-2 p-4 sm:flex-row sm:items-center">
                <CheckCircle2 className={`h-5 w-5 shrink-0 ${d.status === "done" ? "text-emerald-600" : "text-amber-500"}`} />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium">{d.filename}</div>
                  <div className="text-xs muted">{KIND_LABEL[d.kind]}{d.kind === "question_paper" && ` · ${EXAM_LABEL[d.exam_type]}`} · read via {d.extraction_method || "—"}{d.kind !== "syllabus" && ` · ${d.question_count} questions`}</div>
                  {d.notes && <p className="mt-1 whitespace-pre-line text-xs text-ink-soft">{d.notes}</p>}
                </div>
                <span className={`chip shrink-0 ${DOC_STATUS_STYLE[d.status] || ""}`}>{DOC_STATUS_LABEL[d.status] || d.status}</span>
              </div>
            ))}
            {results.filter((d) => d.evaluation).map((d) => <EvaluationCard key={`ev-${d.id}`} ev={d.evaluation!} />)}
          </div>
          {subjectId && (
            <div className="mt-4 flex flex-wrap gap-2">
              <Link to={`/app/subjects/${subjectId}?tab=questions`} className="btn-outline">Review extracted questions</Link>
              <Link to={`/app/subjects/${subjectId}/predictions?exam=SEMESTER`} className="btn-primary">See predictions</Link>
            </div>
          )}
        </div>
      )}

      <Modal open={newSubject} onClose={() => setNewSubject(false)} title="New subject">
        <NewSubjectForm onCreated={(s) => { setNewSubject(false); reloadSubjects(true); setSubjectId(s.id); }} />
      </Modal>

      <Modal open={!!paste} onClose={() => setPaste(null)} title="Paste paper text" wide>
        {paste && (
          <div className="space-y-3">
            <div><label className="label">Title</label><input className="input" value={paste.title} onChange={(e) => setPaste({ ...paste, title: e.target.value })} placeholder="e.g. CAT 1 2024 (typed)" /></div>
            <DocMetaFields value={paste.meta} unitsCount={unitsCount} predictions={predictions || []} onChange={(m) => setPaste({ ...paste, meta: m })} />
            <div><label className="label">Paper text</label>
              <textarea className="input min-h-[220px] font-mono text-xs" value={paste.text} onChange={(e) => setPaste({ ...paste, text: e.target.value })}
                placeholder={"PART A (10 x 2 = 20 marks)\n1. Define protocol.\n2. ...\nPART B (5 x 13 = 65 marks)\n11. (a) Explain the OSI model. (13)\nOr\n(b) ..."} /></div>
            <div className="flex justify-end gap-2">
              <button className="btn-outline" onClick={() => setPaste(null)}>Cancel</button>
              <button className="btn-primary" disabled={!paste.text.trim() || !subjectId || paste.busy} onClick={submitPaste}>{paste.busy && <Spinner />} Analyse text</button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
