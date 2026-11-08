import { AnimatePresence, motion } from "framer-motion";
import { BookmarkPlus, ChevronDown, History, Sparkles, Wand2 } from "lucide-react";
import { useState } from "react";
import type { PredItem } from "../api";
import { EXAM_LABEL, PRIORITY_BAR, QTYPE_LABEL } from "../lib/format";
import { Bar, EvidenceTag, PriorityPill } from "./ui";

export function GeneratedTag() {
  return <span className="chip border border-dashed border-orange-300 bg-orange-50 text-orange-700"><Wand2 className="h-3 w-3" /> Generated wording</span>;
}

export function WordingNote({ it }: { it: PredItem }) {
  if (it.is_generated) {
    return it.evidence === "practice_new"
      ? <p className="text-xs text-orange-700">Practice question written from the syllabus — this topic has not appeared in your uploaded papers.</p>
      : <p className="text-xs text-orange-700">Wording adapted for {it.marks} marks — the concept is real, this exact sentence was not asked.</p>;
  }
  if (it.wording === "past_other_marks") return <p className="text-xs text-sky2-600">Real past wording, asked at different marks.</p>;
  return null;
}

export default function PredictionCard({ it, weights, onPrepare, onSave, rank }: {
  it: PredItem; weights: Record<string, number>; onPrepare: () => void; onSave: () => void; rank?: number;
}) {
  const [open, setOpen] = useState(false);
  const fr = it.frequency;
  return (
    <div className={`rounded-2xl bg-white shadow-soft transition hover:shadow-lift ${it.is_generated ? "border-2 border-dashed border-orange-200" : "border border-line"}`}>
      <div className="p-4 sm:p-5">
        <div className="flex items-start gap-3">
          {rank !== undefined && <div className="hidden w-6 shrink-0 pt-0.5 text-right font-display text-sm font-semibold text-ink-mute sm:block">{rank}</div>}
          <div className="min-w-0 flex-1">
            <div className="mb-2 flex flex-wrap items-center gap-1.5">
              <PriorityPill p={it.priority} />
              <span className="chip bg-stone-100 text-ink-soft">{it.marks} marks</span>
              {it.unit && <span className="chip bg-stone-100 text-ink-soft">Unit {it.unit}</span>}
              <EvidenceTag e={it.evidence} />
              {it.is_generated && <GeneratedTag />}
              {it.qtype !== "theory" && <span className="chip bg-stone-50 text-ink-mute">{QTYPE_LABEL[it.qtype] || it.qtype}</span>}
            </div>
            <p className="text-[15px] leading-relaxed">{it.text}</p>
            <div className="mt-1.5"><WordingNote it={it} /></div>
            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs muted">
              {it.topic && <span className="truncate">Topic: <span className="text-ink-soft">{it.topic}</span></span>}
              <span className="flex items-center gap-1"><History className="h-3.5 w-3.5" />
                {fr.papers ? `Asked in ${fr.papers} of ${fr.total_papers} papers` : "Not asked in uploaded papers"}
                {it.years.length > 0 && ` · ${it.years.join(", ")}`}
              </span>
            </div>
          </div>
          <div className="w-16 shrink-0 text-right sm:w-24">
            <div className="font-display text-xl font-semibold">{Math.round(it.score)}</div>
            <div className="text-[10px] uppercase tracking-wide muted">score</div>
            <div className="mt-1.5"><Bar value={it.score} className={PRIORITY_BAR[it.priority]} /></div>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <button className="btn-accent btn-sm" onClick={onPrepare}><Sparkles className="h-3.5 w-3.5" /> Prepare this question</button>
          <button className="btn-outline btn-sm" onClick={onSave}><BookmarkPlus className="h-3.5 w-3.5" /> Save</button>
          <button className="btn-ghost btn-sm ml-auto" onClick={() => setOpen(!open)}>
            Why this? <ChevronDown className={`h-3.5 w-3.5 transition ${open ? "rotate-180" : ""}`} />
          </button>
        </div>
      </div>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
            <div className="grid gap-5 border-t border-line bg-[#fcfbf8] p-4 sm:p-5 md:grid-cols-2">
              <div>
                <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide muted">Reasons</h4>
                <ul className="space-y-1.5 text-sm text-ink-soft">
                  {it.reasons.map((r, i) => <li key={i} className="flex gap-2"><span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-lav-500" />{r}</li>)}
                </ul>
                <h4 className="mb-1 mt-4 text-xs font-semibold uppercase tracking-wide muted">How to prepare</h4>
                <p className="text-sm text-ink-soft">{it.prep}</p>
                <p className="mt-3 text-xs muted">{it.evidence_label}</p>
              </div>
              <div>
                <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide muted">Score breakdown</h4>
                {it.topic_score !== undefined && it.topic_score !== null && (
                  <div className="mb-3 rounded-xl bg-white px-3 py-2 text-xs ring-1 ring-line">
                    <div className="text-ink-soft">
                      Priority <b className="text-ink">{Math.round(it.score)}</b> = topic score <b className="text-ink">{Math.round(it.topic_score)}</b>
                      {it.topic_rank ? <span className="muted"> (topic #{it.topic_rank})</span> : null} · question score <b className="text-ink">{Math.round(it.question_score ?? it.score)}</b>
                    </div>
                    <div className="mt-0.5 muted">
                      Topics are ranked first ({it.ranker === "ml" ? "ML-assisted" : "statistical"}), then questions within them. Signals below are for this question.
                    </div>
                  </div>
                )}
                <div className="space-y-2">
                  {Object.entries(it.factors).map(([k, v]) => (
                    <div key={k} className="grid grid-cols-[1fr_70px_38px] items-center gap-2 text-xs">
                      <span className="truncate text-ink-soft">{it.factor_labels[k] || k} <span className="muted">· {Math.round((weights[k] || 0) * 100)}%</span></span>
                      <Bar value={v * 100} className="bg-sky2-400" />
                      <span className="text-right tabular-nums muted">{Math.round(v * 100)}</span>
                    </div>
                  ))}
                </div>
                <p className="mt-2 text-[11px] muted">Each signal is 0–100; the score is their weighted sum. It ranks study priority — it is not a probability.</p>
              </div>
              {it.appearances.length > 0 && (
                <div className="md:col-span-2">
                  <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide muted">Previous appearances (real questions from your uploads)</h4>
                  <div className="space-y-1.5">
                    {it.appearances.map((a, i) => (
                      <div key={i} className="flex flex-col gap-1 rounded-xl bg-white px-3 py-2 text-sm ring-1 ring-line sm:flex-row sm:items-center sm:gap-3">
                        <span className="shrink-0 text-xs font-medium text-lav-700">{a.paper}{a.number ? ` · Q${a.number}` : ""}{a.marks ? ` · ${a.marks}m` : ""}</span>
                        <span className="text-ink-soft">{a.text}</span>
                      </div>
                    ))}
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5 text-xs">
                    {Object.entries(it.frequency.by_type).map(([k, v]) => <span key={k} className="chip bg-stone-100 text-ink-soft">{EXAM_LABEL[k] || k} × {v}</span>)}
                  </div>
                </div>
              )}
              {it.variation && (
                <div className="md:col-span-2">
                  <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide muted">Could also be asked as</h4>
                  <div className="rounded-xl border-2 border-dashed border-orange-200 bg-white px-3 py-2 text-sm">
                    <div className="mb-1"><GeneratedTag /></div>
                    {it.variation.text}
                    <div className="mt-1 text-[11px] muted">{it.variation.label}. Never appeared in this exact form.</div>
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
