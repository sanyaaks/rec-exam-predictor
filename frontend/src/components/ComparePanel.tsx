import { ChevronDown, Target, Upload } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, Evaluation } from "../api";
import { EvaluationCard } from "../pages/Upload";
import { MATCH_LABEL, MATCH_STYLE } from "../pages/workspace/Accuracy";
import { EXAM_LABEL } from "../lib/format";
import { useAsync } from "../lib/hooks";
import { errMsg, Spinner, useToast } from "./ui";

function EvalRows({ ev }: { ev: Evaluation }) {
  const [open, setOpen] = useState(false);
  const rows = ev.metrics.rows || [];
  if (!rows.length) return null;
  return (
    <div className="mt-2">
      <button className="btn-ghost btn-sm" onClick={() => setOpen(!open)}>Each question <ChevronDown className={`h-3.5 w-3.5 transition ${open ? "rotate-180" : ""}`} /></button>
      {open && (
        <ul className="mt-2 space-y-1.5">
          {rows.map((r, i) => (
            <li key={i} className="rounded-lg bg-white px-3 py-2 text-sm ring-1 ring-line">
              <div className="flex flex-wrap items-center gap-2">
                <span className={`chip ${MATCH_STYLE[r.match]}`}>{MATCH_LABEL[r.match]}</span>
                <span className="text-xs muted">{r.marks ? `${r.marks} marks` : ""}{r.unit ? ` · Unit ${r.unit}` : ""}{r.topic ? ` · ${r.topic}` : ""}</span>
              </div>
              <div className="mt-1">{r.text}</div>
              {r.predicted && <div className="mt-1 text-xs muted">Predicted: “{r.predicted}”</div>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function ComparePanel({ pid, sid }: { pid: number; sid: number }) {
  const { toast } = useToast();
  const { data: docs } = useAsync(() => api.documents(sid), [sid]);
  const { data: evals, reload } = useAsync(() => api.evaluations(pid), [pid]);
  const [docId, setDocId] = useState<number | "">("");
  const [busy, setBusy] = useState(false);
  const papers = (docs || []).filter((d) => d.kind === "question_paper" && d.question_count > 0);
  const run = async () => {
    if (!docId) return;
    setBusy(true);
    try { await api.evaluatePaper(pid, Number(docId)); reload(true); toast("Compared with the actual paper"); }
    catch (e) { toast(errMsg(e), "error"); } finally { setBusy(false); }
  };
  return (
    <div className="no-print card mx-auto mt-8 max-w-3xl p-5">
      <h3 className="flex items-center gap-2 font-semibold"><Target className="h-4 w-4 text-lav-500" /> Compare with the actual paper</h3>
      <p className="mt-0.5 text-sm muted">After the exam, upload the real paper and compare it with this prediction. The paper then joins your history and improves future predictions.</p>
      <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center">
        <select className="input sm:max-w-md" value={docId} onChange={(e) => setDocId(e.target.value ? Number(e.target.value) : "")}>
          <option value="">Choose an uploaded question paper…</option>
          {papers.map((d) => <option key={d.id} value={d.id}>{d.filename} · {EXAM_LABEL[d.exam_type]} {d.academic_year || d.exam_year || ""}</option>)}
        </select>
        <button className="btn-primary" onClick={run} disabled={!docId || busy}>{busy && <Spinner />} Compare</button>
        <Link to={`/app/upload?subject=${sid}&feedback=${pid}`} className="btn-outline"><Upload className="h-4 w-4" /> Upload actual paper</Link>
      </div>
      {evals && evals.length > 0 && (
        <div className="mt-4 space-y-3">
          {evals.map((ev) => (
            <div key={ev.id}>
              <EvaluationCard ev={ev} compact />
              <EvalRows ev={ev} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
