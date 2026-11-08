import { Download, FileText, Pencil, RefreshCw, Trash2, Upload } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, Doc, downloadFile, PaperSummary, SubjectFull } from "../../api";
import { Empty, errMsg, Modal, Skeleton, Spinner, useToast } from "../../components/ui";
import { DOC_STATUS_LABEL, DOC_STATUS_STYLE, EXAM_LABEL, KIND_LABEL, MONTHS, relTime } from "../../lib/format";
import { useAsync } from "../../lib/hooks";

export function DocMetaFields({ value, onChange, unitsCount, predictions }: { value: Partial<Doc>; onChange: (v: Partial<Doc>) => void; unitsCount: number; predictions?: PaperSummary[] }) {
  const set = (k: keyof Doc, v: unknown) => onChange({ ...value, [k]: v });
  const units = value.units_covered || [];
  return (
    <div className="grid grid-cols-2 gap-3">
      <div>
        <label className="label">Document type</label>
        <select className="input" value={value.kind} onChange={(e) => set("kind", e.target.value)}>
          <option value="question_paper">Question paper</option><option value="syllabus">Syllabus</option><option value="question_bank">Question bank / important Qs</option>
        </select>
      </div>
      {value.kind === "question_paper" && (
        <div>
          <label className="label">Exam</label>
          <select className="input" value={value.exam_type} onChange={(e) => set("exam_type", e.target.value)}>
            <option value="CAT1">CAT 1</option><option value="CAT2">CAT 2</option><option value="SEMESTER">Semester</option>
          </select>
        </div>
      )}
      {value.kind !== "syllabus" && (
        <>
          <div>
            <label className="label">Academic year</label>
            <input className="input" value={value.academic_year || ""} onChange={(e) => set("academic_year", e.target.value)} placeholder="2024-25" />
          </div>
          <div>
            <label className="label">Exam year</label>
            <input className="input" type="number" min={2000} max={2100} value={value.exam_year ?? ""} onChange={(e) => set("exam_year", e.target.value ? Number(e.target.value) : null)} placeholder="2024" />
          </div>
          <div>
            <label className="label">Exam month</label>
            <select className="input" value={value.exam_month ?? ""} onChange={(e) => set("exam_month", e.target.value ? Number(e.target.value) : null)}>
              <option value="">—</option>{MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Units covered (if known)</label>
            <div className="flex flex-wrap gap-1.5 pt-1">
              {Array.from({ length: unitsCount }, (_, i) => i + 1).map((u) => (
                <button type="button" key={u} onClick={() => set("units_covered", units.includes(u) ? units.filter((x) => x !== u) : [...units, u].sort())}
                  className={`h-8 w-8 rounded-lg text-xs font-medium transition ${units.includes(u) ? "bg-lav-500 text-white" : "bg-stone-100 text-ink-soft hover:bg-stone-200"}`}>{u}</button>
              ))}
            </div>
          </div>
          <div>
            <label className="label">Faculty ID (optional)</label>
            <input className="input" value={value.faculty_id || ""} onChange={(e) => set("faculty_id", e.target.value)} placeholder="e.g. who set the paper" />
          </div>
          {predictions && value.kind === "question_paper" && (
            <div className="col-span-2">
              <label className="label">This is the actual paper from an exam I predicted (optional)</label>
              <select className="input" value={value.feedback_for_prediction_id ?? ""} onChange={(e) => set("feedback_for_prediction_id", e.target.value ? Number(e.target.value) : null)}>
                <option value="">— No, just a past paper —</option>
                {predictions.map((p) => <option key={p.id} value={p.id}>{p.title} · {new Date(p.created_at.endsWith("Z") ? p.created_at : p.created_at + "Z").toLocaleDateString()}</option>)}
              </select>
              {value.feedback_for_prediction_id ? <p className="mt-1 text-xs muted">We'll compare this paper with that prediction straight after extraction, then add it to your history.</p> : null}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default function DocumentsTab({ subject, onChange }: { subject: SubjectFull; onChange: () => void }) {
  const { toast, confirm } = useToast();
  const { data, loading, reload } = useAsync(() => api.documents(subject.id), [subject.id]);
  const [editing, setEditing] = useState<Doc | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const [preview, setPreview] = useState<Doc | null>(null);
  const unitsCount = Math.max(subject.exam_config.units_count || 5, subject.units.length);

  const act = async (id: number, fn: () => Promise<unknown>, msg: string) => {
    setBusy(id);
    try { await fn(); toast(msg); reload(true); onChange(); } catch (e) { toast(errMsg(e), "error"); } finally { setBusy(null); }
  };

  const openPreview = async (d: Doc) => {
    try { setPreview(await api.document(d.id)); } catch (e) { toast(errMsg(e), "error"); }
  };

  if (loading && !data) return <div className="space-y-2">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-16" />)}</div>;
  if (!data?.length) {
    return (
      <Empty icon={<FileText className="h-5 w-5" />} title="No documents yet" action={<Link to={`/app/upload?subject=${subject.id}`} className="btn-primary"><Upload className="h-4 w-4" /> Upload papers</Link>}>
        Upload previous CAT and semester papers, the syllabus, and any question banks.
      </Empty>
    );
  }
  return (
    <div className="space-y-2">
      {data.map((d) => (
        <div key={d.id} className="card flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
          <div className="flex min-w-0 flex-1 items-start gap-3">
            <div className="rounded-xl bg-lav-50 p-2 text-lav-600"><FileText className="h-4 w-4" /></div>
            <div className="min-w-0">
              <button onClick={() => openPreview(d)} className="block max-w-full truncate text-left text-sm font-medium hover:text-lav-700">{d.filename}</button>
              <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs muted">
                <span>{KIND_LABEL[d.kind] || d.kind}</span>
                {d.kind === "question_paper" && <span className="chip bg-stone-100 text-ink-soft">{EXAM_LABEL[d.exam_type]}</span>}
                {d.academic_year && <span>{d.academic_year}</span>}
                {d.exam_year && <span>· {d.exam_month ? MONTHS[d.exam_month - 1] + " " : ""}{d.exam_year}</span>}
                {d.kind !== "syllabus" && <span>· {d.question_count} questions</span>}
                {d.extraction_method && <span>· read via {d.extraction_method}</span>}
                {d.is_sample && <span className="chip bg-amber-50 text-amber-700">Sample</span>}
                <span>· {relTime(d.created_at)}</span>
              </div>
              {d.notes && <p className="mt-1 whitespace-pre-line text-xs text-ink-soft">{d.notes}</p>}
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-1">
            <span className={`chip mr-1 ${DOC_STATUS_STYLE[d.status] || ""}`}>{DOC_STATUS_LABEL[d.status] || d.status}</span>
            {busy === d.id ? <Spinner className="mx-2" /> : <>
              <button className="btn-ghost btn-sm" title="Edit details" onClick={() => setEditing(d)}><Pencil className="h-3.5 w-3.5" /></button>
              {d.has_file && <button className="btn-ghost btn-sm" title="Re-run extraction" onClick={() => act(d.id, () => api.reprocess(d.id), "Re-analysed")}><RefreshCw className="h-3.5 w-3.5" /></button>}
              {d.has_file && <button className="btn-ghost btn-sm" title="Download original" onClick={() => downloadFile(`/api/documents/${d.id}/file`, d.filename).catch((e) => toast(errMsg(e), "error"))}><Download className="h-3.5 w-3.5" /></button>}
              <button className="btn-ghost btn-sm text-rose-600" title="Delete" onClick={async () => {
                if (await confirm(`Delete “${d.filename}” and its ${d.question_count} extracted questions?`)) act(d.id, () => api.deleteDocument(d.id), "Deleted");
              }}><Trash2 className="h-3.5 w-3.5" /></button>
            </>}
          </div>
        </div>
      ))}

      <Modal open={!!editing} onClose={() => setEditing(null)} title="Document details">
        {editing && (
          <div className="space-y-4">
            <div><label className="label">Name</label><input className="input" value={editing.filename} onChange={(e) => setEditing({ ...editing, filename: e.target.value })} /></div>
            <DocMetaFields value={editing} onChange={(v) => setEditing({ ...editing, ...v } as Doc)} unitsCount={unitsCount} />
            <p className="text-xs muted">Changing the document type or exam re-runs extraction.</p>
            <div className="flex justify-end gap-2">
              <button className="btn-outline" onClick={() => setEditing(null)}>Cancel</button>
              <button className="btn-primary" onClick={() => {
                const e = editing;
                setEditing(null);
                act(e.id, () => api.patchDocument(e.id, { filename: e.filename, kind: e.kind, exam_type: e.kind === "question_paper" ? e.exam_type : "NA", academic_year: e.academic_year, exam_year: e.exam_year, exam_month: e.exam_month, units_covered: e.units_covered }), "Saved");
              }}>Save</button>
            </div>
          </div>
        )}
      </Modal>

      <Modal open={!!preview} onClose={() => setPreview(null)} title={preview?.filename || ""} wide>
        <div className="text-xs muted">Extracted text (what the system read from the file)</div>
        <pre className="mt-2 max-h-[60vh] overflow-auto whitespace-pre-wrap rounded-xl bg-stone-50 p-3 text-xs leading-relaxed">{preview?.raw_text || "(no text extracted)"}</pre>
      </Modal>
    </div>
  );
}
