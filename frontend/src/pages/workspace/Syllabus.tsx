import { ClipboardPaste, Plus, Tag, Trash2, X } from "lucide-react";
import { useEffect, useState } from "react";
import { api, SubjectFull, Unit } from "../../api";
import { Empty, errMsg, Modal, Spinner, useToast } from "../../components/ui";

export default function SyllabusTab({ subject, onSaved }: { subject: SubjectFull; onSaved: () => void }) {
  const { toast } = useToast();
  const [units, setUnits] = useState<Unit[]>(subject.units);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [paste, setPaste] = useState<{ text: string; preview: Unit[] | null; busy: boolean } | null>(null);
  const [newTopic, setNewTopic] = useState<Record<number, string>>({});
  const [version, setVersion] = useState(subject.syllabus_version || "");
  const [meta, setMeta] = useState<{ unit: number; topic: string; keywords: string; subtopics: string } | null>(null);

  useEffect(() => { setUnits(subject.units); setDirty(false); setVersion(subject.syllabus_version || ""); }, [subject.units, subject.syllabus_version]);

  const openMeta = (i: number, topic: string) => {
    const m = units[i].topic_meta?.[topic] || {};
    setMeta({ unit: i, topic, keywords: (m.keywords || []).join(", "), subtopics: (m.subtopics || []).join(", ") });
  };
  const saveMeta = () => {
    if (!meta) return;
    const split = (v: string) => v.split(",").map((x) => x.trim()).filter(Boolean);
    const u = units[meta.unit];
    update(meta.unit, { topic_meta: { ...(u.topic_meta || {}), [meta.topic]: { keywords: split(meta.keywords), subtopics: split(meta.subtopics) } } });
    setMeta(null);
  };

  const update = (i: number, u: Partial<Unit>) => { setUnits(units.map((x, j) => (j === i ? { ...x, ...u } : x))); setDirty(true); };

  const save = async (list = units) => {
    setSaving(true);
    try {
      await api.putSyllabus(subject.id, list.map((u, i) => ({ ...u, number: u.number || i + 1 })), version);
      toast("Syllabus saved — questions re-mapped to units and topics");
      setDirty(false);
      onSaved();
    } catch (e) { toast(errMsg(e), "error"); } finally { setSaving(false); }
  };

  const parse = async () => {
    if (!paste) return;
    setPaste({ ...paste, busy: true });
    try {
      const r = await api.parseSyllabus(subject.id, paste.text);
      setPaste({ ...paste, busy: false, preview: r.units });
    } catch (e) { toast(errMsg(e), "error"); setPaste({ ...paste, busy: false }); }
  };

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0 max-w-2xl">
          <p className="text-sm muted">Units and topics are used to map every question and to find topics that haven't been asked yet. Click a topic to add keywords or subtopics.</p>
          <p className="mt-1 text-xs muted">Keywords help map questions that use different words (e.g. “three-way handshake” → TCP Connection Management). Acronyms like VLAN are detected automatically.</p>
        </div>
        <div className="flex gap-2">
          <button className="btn-outline btn-sm" onClick={() => setPaste({ text: "", preview: null, busy: false })}><ClipboardPaste className="h-3.5 w-3.5" /> Paste syllabus text</button>
          <button className="btn-outline btn-sm" onClick={() => { setUnits([...units, { number: units.length + 1, title: "", topics: [], hours: null }]); setDirty(true); }}><Plus className="h-3.5 w-3.5" /> Add unit</button>
          <button className="btn-primary btn-sm" disabled={!dirty || saving} onClick={() => save()}>{saving && <Spinner />} Save changes</button>
        </div>
      </div>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <label className="text-xs muted" htmlFor="sv">Syllabus version</label>
        <input id="sv" className="input w-56" placeholder="e.g. R2023 v2" value={version} onChange={(e) => { setVersion(e.target.value); setDirty(true); }} />
      </div>

      {units.length === 0 ? (
        <Empty title="No syllabus yet" action={<button className="btn-primary" onClick={() => setPaste({ text: "", preview: null, busy: false })}>Paste syllabus text</button>}>
          Upload the syllabus PDF from the Upload page, paste the text, or add units manually.
        </Empty>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {units.map((u, i) => (
            <div key={i} className="card p-4">
              <div className="flex items-center gap-2">
                <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-lav-100 text-sm font-semibold text-lav-700">{u.number}</span>
                <input className="input font-medium" value={u.title} placeholder="Unit title" onChange={(e) => update(i, { title: e.target.value })} />
                <input className="input w-20" type="number" placeholder="Hrs" title="Teaching hours (used to weigh units)" value={u.hours ?? ""} onChange={(e) => update(i, { hours: e.target.value ? Number(e.target.value) : null })} />
                <button className="btn-ghost btn-sm text-rose-600" onClick={() => { setUnits(units.filter((_, j) => j !== i)); setDirty(true); }}><Trash2 className="h-3.5 w-3.5" /></button>
              </div>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {u.topics.map((t, j) => {
                  const m = u.topic_meta?.[t];
                  const n = (m?.keywords?.length || 0) + (m?.subtopics?.length || 0);
                  return (
                  <span key={j} className={`chip ${n ? "bg-lav-50 text-lav-700 ring-1 ring-lav-200" : "bg-stone-100 text-ink-soft"}`}>
                    <button onClick={() => openMeta(i, t)} className="flex items-center gap-1 hover:underline" title="Keywords & subtopics">{t}{n ? <><Tag className="h-3 w-3" />{n}</> : null}</button><button onClick={() => update(i, { topics: u.topics.filter((_, k) => k !== j) })} className="hover:text-rose-600"><X className="h-3 w-3" /></button>
                  </span>
                  );
                })}
              </div>
              <form className="mt-2 flex gap-2" onSubmit={(e) => {
                e.preventDefault();
                const t = (newTopic[i] || "").trim();
                if (!t) return;
                update(i, { topics: [...u.topics, ...t.split(/[,;–]/).map((x) => x.trim()).filter(Boolean)] });
                setNewTopic({ ...newTopic, [i]: "" });
              }}>
                <input className="input" placeholder="Add topics (comma separated)" value={newTopic[i] || ""} onChange={(e) => setNewTopic({ ...newTopic, [i]: e.target.value })} />
                <button className="btn-outline btn-sm">Add</button>
              </form>
            </div>
          ))}
        </div>
      )}

      <Modal open={!!meta} onClose={() => setMeta(null)} title={meta ? `Topic: ${meta.topic}` : ""}>
        {meta && (
          <div className="space-y-3">
            <label className="block"><span className="label">Keywords (comma separated)</span>
              <input className="input" value={meta.keywords} placeholder="three-way handshake, connection establishment" onChange={(e) => setMeta({ ...meta, keywords: e.target.value })} />
              <span className="mt-1 block text-xs muted">A question containing any keyword is mapped to this topic.</span>
            </label>
            <label className="block"><span className="label">Subtopics (comma separated)</span>
              <input className="input" value={meta.subtopics} placeholder="SMTP, POP3, IMAP" onChange={(e) => setMeta({ ...meta, subtopics: e.target.value })} />
              <span className="mt-1 block text-xs muted">Subtopics in brackets in the topic name are detected automatically.</span>
            </label>
            <div className="flex justify-end gap-2">
              <button className="btn-outline" onClick={() => setMeta(null)}>Cancel</button>
              <button className="btn-primary" onClick={saveMeta}>Done</button>
            </div>
            <p className="text-xs muted">Remember to click “Save changes” to re-map questions.</p>
          </div>
        )}
      </Modal>

      <Modal open={!!paste} onClose={() => setPaste(null)} title="Paste syllabus text" wide>
        {paste && (paste.preview ? (
          <div className="space-y-3">
            <p className="text-sm muted">Found {paste.preview.length} units. This will replace the current syllabus.</p>
            <div className="max-h-[50vh] space-y-2 overflow-y-auto">
              {paste.preview.map((u) => (
                <div key={u.number} className="rounded-xl bg-stone-50 p-3">
                  <div className="text-sm font-medium">Unit {u.number}: {u.title} {u.hours ? <span className="muted">· {u.hours} hrs</span> : null}</div>
                  <div className="mt-1 text-xs muted">{u.topics.join(" · ")}</div>
                </div>
              ))}
            </div>
            <div className="flex justify-end gap-2">
              <button className="btn-outline" onClick={() => setPaste({ ...paste, preview: null })}>Back</button>
              <button className="btn-primary" onClick={() => { const p = paste.preview!; setPaste(null); setUnits(p); save(p); }}>Use this syllabus</button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <textarea className="input min-h-[260px] font-mono text-xs" value={paste.text} onChange={(e) => setPaste({ ...paste, text: e.target.value })}
              placeholder={"UNIT I  INTRODUCTION  9\nData Communication – Networks – Network Types – ...\nUNIT II  TRANSPORT LAYER  9\n..."} />
            <div className="flex justify-end"><button className="btn-primary" disabled={!paste.text.trim() || paste.busy} onClick={parse}>{paste.busy && <Spinner />} Detect units</button></div>
          </div>
        ))}
      </Modal>
    </div>
  );
}
