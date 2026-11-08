import { BookmarkPlus, Lightbulb, ListChecks, Ruler, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { api, PredItem, Prepared } from "../api";
import { Drawer, errMsg, Notice, Skeleton, useToast } from "./ui";

export function useSaveQuestion(subjectId: number) {
  const { toast } = useToast();
  return async (it: PredItem) => {
    try {
      await api.save({ subject_id: subjectId, text: it.text, marks: it.marks, unit: it.unit, topic: it.topic, evidence: it.evidence, priority: it.priority });
      toast("Saved to your study list");
    } catch (e) {
      toast(errMsg(e), "error");
    }
  };
}

export default function PreparePanel({ subjectId, item, onClose }: { subjectId: number; item: PredItem | null; onClose: () => void }) {
  const [data, setData] = useState<Prepared | null>(null);
  const [error, setError] = useState<string | null>(null);
  const save = useSaveQuestion(subjectId);

  useEffect(() => {
    if (!item) return;
    setData(null);
    setError(null);
    api.prepare(subjectId, {
      text: item.text, marks: item.marks, qtype: item.qtype, topic: item.topic, unit: item.unit,
      related: item.appearances.map((a) => a.text).filter((t) => t !== item.text),
    }).then(setData).catch((e) => setError(errMsg(e)));
  }, [item, subjectId]);

  return (
    <Drawer open={!!item} onClose={onClose} title={<span className="flex items-center gap-2"><Sparkles className="h-4 w-4 text-lav-500" /> Prepare this question</span>}>
      {item && (
        <div className="space-y-5">
          <div className="card p-4">
            <div className="text-[15px] font-medium leading-relaxed">{item.text}</div>
            <div className="mt-2 flex flex-wrap gap-1.5 text-xs">
              <span className="chip bg-stone-100 text-ink-soft">{item.marks} marks</span>
              {item.unit && <span className="chip bg-stone-100 text-ink-soft">Unit {item.unit}</span>}
              {item.topic && <span className="chip bg-lav-50 text-lav-700">{item.topic}</span>}
            </div>
            <button className="btn-outline btn-sm mt-3" onClick={() => save(item)}><BookmarkPlus className="h-3.5 w-3.5" /> Save to study list</button>
          </div>

          {error && <Notice tone="warn">{error}</Notice>}
          {!data && !error && (
            <div className="space-y-3">
              <Skeleton className="h-4 w-2/3" /><Skeleton className="h-24" /><Skeleton className="h-4 w-1/2" /><Skeleton className="h-32" />
              <p className="text-xs muted">Preparing an exam-oriented answer… AI answers can take up to a minute.</p>
            </div>
          )}
          {data && (
            <>
              <Notice tone={data.mode === "ai" ? "info" : "warn"}>{data.disclaimer}</Notice>

              <div className="grid gap-3 sm:grid-cols-2">
                <div className="card p-4">
                  <div className="mb-2 flex items-center gap-2 text-xs font-medium muted"><Ruler className="h-3.5 w-3.5" /> Suggested length</div>
                  <p className="text-sm">{data.length_guide}</p>
                  {data.diagram_expected && <p className="mt-2 text-xs text-lav-700">A labelled diagram is expected for this answer.</p>}
                </div>
                <div className="card p-4">
                  <div className="mb-2 flex items-center gap-2 text-xs font-medium muted"><Lightbulb className="h-3.5 w-3.5" /> Keywords to underline</div>
                  <div className="flex flex-wrap gap-1.5">
                    {data.keywords.map((k) => <span key={k} className="chip bg-lav-50 text-lav-700">{k}</span>)}
                  </div>
                </div>
              </div>

              {data.answer_markdown ? (
                <div className="card p-5">
                  <div className="mb-2 text-xs font-medium muted">Exam-oriented answer</div>
                  <div className="prose-answer text-sm text-ink"><ReactMarkdown>{data.answer_markdown}</ReactMarkdown></div>
                </div>
              ) : null}

              <div className="card p-5">
                <div className="mb-3 flex items-center gap-2 text-xs font-medium muted"><ListChecks className="h-3.5 w-3.5" /> Answer structure (expected subheadings)</div>
                <ol className="space-y-3">
                  {data.outline.map((s, i) => (
                    <li key={i} className="flex gap-3">
                      <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-lav-100 text-xs font-semibold text-lav-700">{i + 1}</span>
                      <div>
                        <div className="text-sm font-medium">{s.heading}</div>
                        <ul className="mt-0.5 list-disc pl-4 text-sm text-ink-soft">{s.points.map((p, j) => <li key={j}>{p}</li>)}</ul>
                      </div>
                    </li>
                  ))}
                </ol>
              </div>

              {data.related_questions.length > 0 && (
                <div className="card p-5">
                  <div className="mb-2 text-xs font-medium muted">The same concept was asked as</div>
                  <ul className="space-y-1.5 text-sm text-ink-soft">{data.related_questions.map((q, i) => <li key={i}>“{q}”</li>)}</ul>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </Drawer>
  );
}
