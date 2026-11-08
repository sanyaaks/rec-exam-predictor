import { BookmarkPlus, FileDown, Printer, RefreshCw, Sparkles, Trash2 } from "lucide-react";
import { Fragment, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, downloadFile, PredItem } from "../api";
import ComparePanel from "../components/ComparePanel";
import { RankerBadge } from "../components/EngineWidgets";
import { GeneratedTag, WordingNote } from "../components/PredictionCard";
import PreparePanel, { useSaveQuestion } from "../components/PreparePanel";
import { errMsg, EvidenceTag, Notice, PageLoader, PriorityPill, Spinner, useToast } from "../components/ui";
import { EXAM_LABEL, relTime } from "../lib/format";
import { useAsync } from "../lib/hooks";

function QuestionBody({ it, notes, onPrepare, onSave }: { it: PredItem; notes: boolean; onPrepare: () => void; onSave: () => void }) {
  return (
    <div className="group">
      <div className={it.is_generated && notes ? "rounded-md border border-dashed border-orange-300 px-1.5 py-0.5" : ""}>{it.text}</div>
      {notes && (
        <div className="paper-notes mt-1 flex flex-wrap items-center gap-1.5 font-sans text-[11px]">
          <PriorityPill p={it.priority} />
          <span className="text-ink-mute">score {Math.round(it.score)}</span>
          {it.unit && <span className="text-ink-mute">· Unit {it.unit}</span>}
          {it.topic && <span className="text-ink-mute">· {it.topic}</span>}
          <EvidenceTag e={it.evidence} />
          {it.is_generated && <GeneratedTag />}
          <span className="text-ink-mute">{it.frequency.papers ? `· asked in ${it.frequency.papers}/${it.frequency.total_papers} papers${it.years.length ? ` (${it.years.join(", ")})` : ""}` : "· not in uploaded papers"}</span>
          <span className="no-print ml-1 inline-flex gap-1">
            <button className="rounded-md px-1.5 py-0.5 text-lav-700 hover:bg-lav-50" onClick={onPrepare}><Sparkles className="inline h-3 w-3" /> Prepare</button>
            <button className="rounded-md px-1.5 py-0.5 text-ink-soft hover:bg-stone-100" onClick={onSave}><BookmarkPlus className="inline h-3 w-3" /> Save</button>
          </span>
          <div className="w-full"><WordingNote it={it} /></div>
        </div>
      )}
    </div>
  );
}

export default function PaperPage() {
  const id = Number(useParams().id);
  const nav = useNavigate();
  const { toast, confirm } = useToast();
  const { data, error } = useAsync(() => api.paper(id), [id]);
  const sid = data?.subject.id;
  const { data: history, reload: reloadHistory } = useAsync(() => (sid ? api.papers(sid) : Promise.resolve([])), [sid]);
  const [notes, setNotes] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [preparing, setPreparing] = useState<PredItem | null>(null);
  const save = useSaveQuestion(sid || 0);

  if (error) return <Notice tone="warn">{error}</Notice>;
  if (!data) return <PageLoader label="Loading paper…" />;
  const { paper, subject } = data;

  const another = async () => {
    setBusy("regen");
    try { const r = await api.generatePaper(subject.id, paper.exam_type, Math.floor(Math.random() * 1e6) + 1, paper.units); nav(`/app/papers/${r.id}`); }
    catch (e) { toast(errMsg(e), "error"); } finally { setBusy(null); }
  };
  const pdf = async () => {
    setBusy("pdf");
    try { await downloadFile(`/api/papers/${id}/pdf?notes=${notes}`, "predicted_paper.pdf"); } catch (e) { toast(errMsg(e), "error"); } finally { setBusy(null); }
  };

  return (
    <div>
      <div className="no-print mb-5 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <Link to={`/app/subjects/${subject.id}/predictions?exam=${paper.exam_type}`} className="text-xs font-medium uppercase tracking-wide text-lav-600 hover:underline">{subject.name}</Link>
          <h1 className="text-2xl font-semibold">{data.title}</h1>
          <p className="text-sm muted">Generated {relTime(data.created_at)} · {paper.seed ? "alternative set" : "top-ranked set"}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <label className="btn-outline cursor-pointer">
            <input type="checkbox" className="accent-lav-500" checked={notes} onChange={(e) => setNotes(e.target.checked)} /> Show prediction notes
          </label>
          <button className="btn-outline" onClick={() => window.print()}><Printer className="h-4 w-4" /> Print</button>
          <button className="btn-outline" onClick={pdf} disabled={!!busy}>{busy === "pdf" ? <Spinner /> : <FileDown className="h-4 w-4" />} Download PDF</button>
          <button className="btn-primary" onClick={another} disabled={!!busy}>{busy === "regen" ? <Spinner /> : <RefreshCw className="h-4 w-4" />} Generate another set</button>
        </div>
      </div>

      <div className="no-print mb-4 space-y-2">
        <Notice tone={paper.confidence.level === "low" ? "warn" : "info"}>
          <b>Predicted paper — not an official examination paper; not guaranteed.</b> Questions are ranked from your uploaded papers and syllabus. {paper.confidence.level === "low" && paper.confidence.message}
        </Notice>
        {paper.ranker_info && <RankerBadge r={paper.ranker_info} />}
        {notes && <p className="text-xs muted">Questions with a dashed orange outline use generated wording; the rest are real past questions. Click “Prepare” for answers and preparation notes.</p>}
      </div>

      <div className="print-area paper-sheet mx-auto max-w-3xl rounded-sm border border-line bg-white px-5 py-8 text-[15px] text-black shadow-lift sm:px-12 sm:py-12">
        <div className="text-center">
          <div className="font-sans text-[10px] uppercase tracking-[0.2em] text-stone-500">Predicted question paper</div>
          <div className="mt-2 text-lg font-bold uppercase">{subject.code ? `${subject.code} — ` : ""}{subject.name}</div>
          <div className="mt-1 text-sm">{paper.label} · Regulation {subject.regulation} · Semester {subject.semester}{subject.department ? ` · ${subject.department}` : ""}</div>
        </div>
        <div className="mt-4 flex flex-wrap justify-between gap-2 border-y border-black py-1.5 text-sm">
          <span>Time: {paper.duration}</span>
          <span>Units: {paper.units.join(", ")}</span>
          <span>Maximum: {paper.total_marks} marks</span>
        </div>

        {paper.sections.map((sec) => (
          <section key={sec.name} className="mt-7">
            <h2 className="text-center font-bold" style={{ fontFamily: "inherit" }}>{sec.title} — ({sec.count} × {sec.marks_each} = {sec.total} marks)</h2>
            {sec.instruction && <p className="mt-0.5 text-center text-sm italic">{sec.instruction}</p>}
            <div className="mt-4 space-y-4">
              {sec.questions.map((q) => (
                <div key={q.number} className="grid grid-cols-[2rem_1fr_2.5rem] gap-x-2" style={{ breakInside: "avoid" }}>
                  {q.options.map((opt, k) => (
                    <Fragment key={opt.id}>
                      <div className="font-semibold">{k === 0 ? `${q.number}.` : ""}</div>
                      <div className="flex gap-2">
                        {q.options.length > 1 && <span className="shrink-0">({"ab"[k]})</span>}
                        <div className="min-w-0 flex-1"><QuestionBody it={opt} notes={notes} onPrepare={() => setPreparing(opt)} onSave={() => save(opt)} /></div>
                      </div>
                      <div className="text-right text-sm">({opt.marks})</div>
                      {k === 0 && q.options.length > 1 && <><div /><div className="py-1 text-center text-sm font-bold">OR</div><div /></>}
                    </Fragment>
                  ))}
                </div>
              ))}
            </div>
          </section>
        ))}
        <p className="mt-10 border-t border-stone-200 pt-3 text-center font-sans text-[10px] text-stone-500">
          Predicted paper generated from past-paper analysis. Not an official REC / Anna University examination paper. Predictions are not guaranteed.
        </p>
      </div>

      {history && history.length > 1 && (
        <div className="no-print card mx-auto mt-8 max-w-3xl p-5">
          <h3 className="mb-2 font-semibold">Previous predictions for this subject</h3>
          <ul className="divide-y divide-line">
            {history.map((h) => (
              <li key={h.id} className={`flex items-center gap-3 py-2 text-sm ${h.id === id ? "font-medium" : ""}`}>
                <Link to={`/app/papers/${h.id}`} className="min-w-0 flex-1 truncate hover:text-lav-700">{h.title}</Link>
                {h.ranker === "ml" && <span className="chip shrink-0 bg-lav-50 text-lav-700">ML-assisted</span>}
                {h.evaluated && <span className="chip shrink-0 bg-emerald-50 text-emerald-700">Compared</span>}
                <span className="shrink-0 text-xs muted">{EXAM_LABEL[h.exam_type]} · {relTime(h.created_at)}</span>
                {h.id !== id && (
                  <button className="btn-ghost btn-sm text-rose-600" onClick={async () => {
                    if (await confirm("Delete this saved prediction?")) { await api.deletePaper(h.id); reloadHistory(true); }
                  }}><Trash2 className="h-3.5 w-3.5" /></button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
      <ComparePanel pid={id} sid={subject.id} />
      {sid && <PreparePanel subjectId={sid} item={preparing} onClose={() => setPreparing(null)} />}
    </div>
  );
}
