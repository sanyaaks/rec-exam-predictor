import { CheckCircle2, Plus, RotateCcw, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ClassificationCfg, ExamConfig, ExamType, Section, SubjectFull, Weights } from "../../api";
import { EngineLine } from "./Accuracy";
import { errMsg, Notice, Segmented, Spinner, useToast } from "../../components/ui";
import { EXAM_LABEL } from "../../lib/format";
import { useMeta } from "../../lib/hooks";

export default function SettingsTab({ subject, onSaved }: { subject: SubjectFull; onSaved: () => void }) {
  const nav = useNavigate();
  const meta = useMeta();
  const { toast, confirm } = useToast();
  const [cfg, setCfg] = useState<ExamConfig>(subject.exam_config);
  const [wByType, setWByType] = useState<Record<ExamType, Weights>>(subject.weights_by_type);
  const [info, setInfo] = useState({ name: subject.name, code: subject.code, department: subject.department, regulation: subject.regulation, semester: subject.semester });
  const [et, setEt] = useState<ExamType>("CAT1");
  const [wEt, setWEt] = useState<ExamType>("SEMESTER");
  const weights = wByType[wEt] || subject.weights;
  const setWeights = (w: Weights) => setWByType({ ...wByType, [wEt]: w });
  const cls: ClassificationCfg = cfg.classification || { min_similarity: 0.14, keyword_score: 0.8, name_match_score: 0.6 };
  const setCls = (c: Partial<ClassificationCfg>) => setCfg({ ...cfg, classification: { ...cls, ...c } });
  const [saving, setSaving] = useState<string | null>(null);

  useEffect(() => { setCfg(subject.exam_config); setWByType(subject.weights_by_type); }, [subject]);

  const pattern = cfg[et];
  const setPattern = (p: Partial<typeof pattern>) => setCfg({ ...cfg, [et]: { ...pattern, ...p } });
  const setSection = (i: number, s: Partial<Section>) => setPattern({ sections: pattern.sections.map((x, j) => (j === i ? { ...x, ...s } : x)) });
  const unitCount = Math.max(cfg.units_count || 5, subject.units.length);
  const total = pattern.sections.reduce((s, x) => s + (x.count || 0) * (x.marks_each || 0), 0);
  const wsum = Object.values(weights).reduce((a, b) => a + b, 0) || 1;

  const save = async (what: "pattern" | "weights" | "info" | "classification") => {
    setSaving(what);
    try {
      if (what === "pattern") await api.patchSubject(subject.id, { exam_config: { ...cfg, [et]: { ...cfg[et], confirmed: true } } });
      if (what === "classification") await api.patchSubject(subject.id, { exam_config: cfg });
      if (what === "weights") await api.patchSubject(subject.id, { weights: wByType });
      if (what === "info") await api.patchSubject(subject.id, info);
      toast("Saved");
      onSaved();
    } catch (e) { toast(errMsg(e), "error"); } finally { setSaving(null); }
  };

  return (
    <div className="space-y-5">
      {/* exam pattern */}
      <section className="card p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="font-semibold">Examination pattern</h3>
            <p className="text-sm muted">Match this to your actual question paper. Patterns vary across subjects and regulations.</p>
          </div>
          <Segmented<ExamType> value={et} onChange={setEt} options={(["CAT1", "CAT2", "SEMESTER"] as ExamType[]).map((t) => ({ id: t, label: EXAM_LABEL[t] }))} />
        </div>
        <div className="mb-4">
          {subject.exam_config[et].confirmed
            ? <span className="chip bg-emerald-50 text-emerald-700"><CheckCircle2 className="h-3 w-3" /> Pattern confirmed</span>
            : <span className="chip bg-amber-50 text-amber-700">Default pattern — please confirm it matches your {EXAM_LABEL[et]} paper and save</span>}
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <div><label className="label">Display name</label><input className="input" value={pattern.label} onChange={(e) => setPattern({ label: e.target.value })} /></div>
          <div><label className="label">Duration</label><input className="input" value={pattern.duration} onChange={(e) => setPattern({ duration: e.target.value })} /></div>
          <div>
            <label className="label">Units in scope</label>
            <div className="flex flex-wrap gap-1.5 pt-1">
              {Array.from({ length: unitCount }, (_, i) => i + 1).map((u) => (
                <button key={u} onClick={() => setPattern({ units: pattern.units.includes(u) ? pattern.units.filter((x) => x !== u) : [...pattern.units, u].sort((a, b) => a - b) })}
                  className={`h-8 w-8 rounded-lg text-xs font-medium ${pattern.units.includes(u) ? "bg-lav-500 text-white" : "bg-stone-100 text-ink-soft"}`}>{u}</button>
              ))}
            </div>
          </div>
        </div>

        <div className="mt-5 space-y-2">
          {pattern.sections.map((s, i) => (
            <div key={i} className="grid grid-cols-2 gap-2 rounded-xl bg-stone-50 p-3 sm:grid-cols-[90px_1fr_90px_90px_150px_auto] sm:items-end">
              <div><label className="label">Section</label><input className="input" value={s.title} onChange={(e) => setSection(i, { title: e.target.value, name: e.target.value.replace(/part\s*/i, "").trim().slice(0, 2) || s.name })} /></div>
              <div className="col-span-2 sm:col-span-1"><label className="label">Instruction</label><input className="input" value={s.instruction || ""} onChange={(e) => setSection(i, { instruction: e.target.value })} /></div>
              <div><label className="label">Questions</label><input className="input" type="number" min={1} value={s.count} onChange={(e) => setSection(i, { count: Number(e.target.value) })} /></div>
              <div><label className="label">Marks each</label><input className="input" type="number" min={1} value={s.marks_each} onChange={(e) => setSection(i, { marks_each: Number(e.target.value) })} /></div>
              <div><label className="label">Choice</label>
                <select className="input" value={s.choice} onChange={(e) => setSection(i, { choice: e.target.value as Section["choice"] })}>
                  <option value="none">Answer all</option><option value="either_or">Either (a) or (b)</option>
                </select></div>
              <button className="btn-ghost btn-sm text-rose-600 sm:mb-1" onClick={() => setPattern({ sections: pattern.sections.filter((_, j) => j !== i) })} disabled={pattern.sections.length <= 1}><Trash2 className="h-3.5 w-3.5" /></button>
            </div>
          ))}
        </div>
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
          <button className="btn-outline btn-sm" onClick={() => {
            const letter = String.fromCharCode(65 + pattern.sections.length);
            setPattern({ sections: [...pattern.sections, { name: letter, title: `PART ${letter}`, marks_each: 13, count: 1, choice: "either_or", instruction: "" }] });
          }}><Plus className="h-3.5 w-3.5" /> Add section</button>
          <span className="text-sm muted">Total: <b className="text-ink">{total} marks</b></span>
        </div>

        <div className="mt-5 border-t border-line pt-4">
          <h4 className="text-sm font-medium">Topic ranking for {EXAM_LABEL[et]}</h4>
          <select className="input mt-2 sm:max-w-md" value={pattern.ranker || "auto"} onChange={(e) => setPattern({ ranker: e.target.value as "auto" | "statistical" })}>
            <option value="auto">Automatic — use a validated ML model when one exists</option>
            <option value="statistical">Statistical only (frequency, recency, syllabus, unit rotation)</option>
          </select>
          <p className="mt-1 text-xs muted">ML models are trained and validated in the Accuracy tab. Without enough history the statistical ranker is always used.</p>
        </div>

        <div className="mt-5 border-t border-line pt-4">
          <h4 className="text-sm font-medium">Priority thresholds (score)</h4>
          <div className="mt-2 grid grid-cols-3 gap-3 sm:max-w-md">
            {(["very_high", "high", "moderate"] as const).map((k) => (
              <div key={k}><label className="label">{k === "very_high" ? "Very high ≥" : k === "high" ? "High ≥" : "Moderate ≥"}</label>
                <input className="input" type="number" value={cfg.priority_thresholds[k]} onChange={(e) => setCfg({ ...cfg, priority_thresholds: { ...cfg.priority_thresholds, [k]: Number(e.target.value) } })} /></div>
            ))}
          </div>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          {meta && <button className="btn-ghost" onClick={() => setCfg({ ...cfg, [et]: meta.default_exam_config[et] })}><RotateCcw className="h-4 w-4" /> Reset {EXAM_LABEL[et]} to default</button>}
          <button className="btn-primary" onClick={() => save("pattern")} disabled={!!saving}>{saving === "pattern" && <Spinner />} Save pattern</button>
        </div>
      </section>

      {/* weights */}
      <section className="card p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="font-semibold">Scoring weights</h3>
            <p className="text-sm muted">How much each signal counts toward topic and question scores, set separately for each exam type. Weights are normalised to 100%. The Accuracy tab shows which weighting would have worked best on your past papers.</p>
          </div>
          <Segmented<ExamType> value={wEt} onChange={setWEt} options={(["CAT1", "CAT2", "SEMESTER"] as ExamType[]).map((t) => ({ id: t, label: EXAM_LABEL[t] }))} />
        </div>
        <div className="mt-4 space-y-3">
          {Object.keys(weights).map((k) => (
            <div key={k} className="grid grid-cols-[1fr_auto] items-center gap-x-4 gap-y-1 sm:grid-cols-[220px_1fr_60px]">
              <label className="text-sm">{meta?.weight_labels[k] || k}</label>
              <span className="text-right text-sm font-medium tabular-nums sm:order-last">{Math.round((weights[k] / wsum) * 100)}%</span>
              <input type="range" min={0} max={1} step={0.01} value={weights[k]} className="col-span-2 accent-lav-500 sm:col-span-1" onChange={(e) => setWeights({ ...weights, [k]: Number(e.target.value) })} />
            </div>
          ))}
        </div>
        <Notice>These weights are a configurable heuristic, not scientifically proven probabilities.</Notice>
        <div className="mt-4 flex justify-end gap-2">
          {meta && <button className="btn-ghost" onClick={() => setWeights(meta.default_weights)}><RotateCcw className="h-4 w-4" /> Defaults</button>}
          <button className="btn-primary" onClick={() => save("weights")} disabled={!!saving || wsum <= 0}>{saving === "weights" && <Spinner />} Save weights</button>
        </div>
      </section>

      {/* classification */}
      <section className="card p-5">
        <h3 className="font-semibold">Topic classification</h3>
        <p className="text-sm muted">How strictly questions are matched to syllabus topics. Below the minimum similarity a question stays unmapped and appears in the Review tab instead of being guessed.</p>
        <div className="mt-4 space-y-3">
          {([
            ["min_similarity", "Minimum similarity", 0.05, 0.4, 0.01],
            ["keyword_score", "Keyword match strength", 0.3, 1, 0.05],
            ["name_match_score", "Topic-name match strength", 0.3, 1, 0.05],
          ] as [keyof ClassificationCfg, string, number, number, number][]).map(([k, label, min, max, step]) => (
            <div key={k} className="grid grid-cols-[1fr_auto] items-center gap-x-4 gap-y-1 sm:grid-cols-[220px_1fr_60px]">
              <label className="text-sm">{label}</label>
              <span className="text-right text-sm font-medium tabular-nums sm:order-last">{cls[k].toFixed(2)}</span>
              <input type="range" min={min} max={max} step={step} value={cls[k]} className="col-span-2 accent-lav-500 sm:col-span-1" onChange={(e) => setCls({ [k]: Number(e.target.value) })} />
            </div>
          ))}
        </div>
        <p className="mt-2 text-xs muted">Add topic keywords in the Syllabus tab. Saving re-maps questions you haven't checked yourself.</p>
        <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
          <EngineLine />
          <button className="btn-primary" onClick={() => save("classification")} disabled={!!saving}>{saving === "classification" && <Spinner />} Save classification</button>
        </div>
      </section>

      {/* subject info */}
      <section className="card p-5">
        <h3 className="mb-3 font-semibold">Subject details</h3>
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="sm:col-span-3"><label className="label">Name</label><input className="input" value={info.name} onChange={(e) => setInfo({ ...info, name: e.target.value })} /></div>
          <div><label className="label">Code</label><input className="input" value={info.code} onChange={(e) => setInfo({ ...info, code: e.target.value })} /></div>
          <div><label className="label">Department</label><input className="input" value={info.department} onChange={(e) => setInfo({ ...info, department: e.target.value })} /></div>
          <div className="grid grid-cols-2 gap-2">
            <div><label className="label">Regulation</label><input className="input" value={info.regulation} onChange={(e) => setInfo({ ...info, regulation: e.target.value })} /></div>
            <div><label className="label">Semester</label><input className="input" type="number" min={1} max={8} value={info.semester} onChange={(e) => setInfo({ ...info, semester: Number(e.target.value) })} /></div>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap justify-between gap-2">
          <button className="btn border border-rose-200 text-rose-700 hover:bg-rose-50" onClick={async () => {
            if (await confirm(`Delete “${subject.name}” with all its papers, questions and predictions? This cannot be undone.`, "Delete subject")) {
              try { await api.deleteSubject(subject.id); nav("/app/subjects"); } catch (e) { toast(errMsg(e), "error"); }
            }
          }}><Trash2 className="h-4 w-4" /> Delete subject</button>
          <button className="btn-primary" onClick={() => save("info")} disabled={!!saving}>{saving === "info" && <Spinner />} Save details</button>
        </div>
      </section>
    </div>
  );
}
