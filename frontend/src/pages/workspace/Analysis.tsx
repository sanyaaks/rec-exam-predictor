import { BarChart3 } from "lucide-react";
import { Bar as RBar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, SubjectFull, TopicStatus } from "../../api";
import { Bar, Empty, errMsg, Notice, PriorityPill, Skeleton, Stat, useToast } from "../../components/ui";
import { EXAM_LABEL, PRIORITY_HEX, QTYPE_LABEL, STATUS_LABEL, STATUS_STYLE, STATUSES } from "../../lib/format";
import { useAsync } from "../../lib/hooks";
import { useTheme } from "../../lib/theme";

// Semester series is navy on light backgrounds and a light lavender-grey on dark ones
const palette = (dark: boolean) => ({ CAT1: "#a99cf8", CAT2: "#7aa2e8", SEMESTER: dark ? "#d6d3f0" : "#1f2440" });
const PIE = ["#8b7cf6", "#5b86d9", "#a99cf8", "#7aa2e8", "#c4b5fd", "#94a3b8", "#cbd5e1"];
const axis = { fontSize: 11, fill: "#7c8098" };

function ChartCard({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="card p-5">
      <h3 className="font-semibold">{title}</h3>
      {hint && <p className="mb-3 text-xs muted">{hint}</p>}
      <div className="h-60">{children}</div>
    </div>
  );
}

function Tracker({ subject }: { subject: SubjectFull }) {
  const { toast } = useToast();
  const { data, setData } = useAsync(() => api.progress(subject.id), [subject.id]);
  if (!data) return <Skeleton className="h-40" />;
  if (!data.units.length) return <Empty title="Add the syllabus to track topics">The tracker lists every syllabus topic, unit by unit.</Empty>;

  const set = async (unit: number, topic: string, status: TopicStatus) => {
    setData((d) => {
      if (!d) return d;
      const units = d.units.map((u) => u.unit !== unit ? u : {
        ...u, topics: u.topics.map((t) => (t.topic === topic ? { ...t, status } : t)),
      }).map((u) => ({ ...u, completed: u.topics.filter((t) => t.status === "completed").length }));
      const completed = units.reduce((s, u) => s + u.completed, 0);
      return { ...d, units, completed, percent: d.total ? Math.round((100 * completed) / d.total) : 0 };
    });
    try { await api.setProgress(subject.id, { unit, topic, status }); } catch (e) { toast(errMsg(e), "error"); }
  };

  return (
    <div className="card p-5">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
        <div>
          <h3 className="font-semibold">Preparation tracker</h3>
          <p className="text-xs muted">Mark each topic as you go. {data.completed} of {data.total} completed.</p>
        </div>
        <div className="w-40"><div className="mb-1 text-right text-xs muted">{data.percent}%</div><Bar value={data.percent} className="bg-emerald-500" /></div>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {data.units.map((u) => (
          <div key={u.unit} className="rounded-xl border border-line p-3">
            <div className="mb-2 flex items-center justify-between text-sm font-medium">
              <span className="truncate">Unit {u.unit} · {u.title}</span><span className="shrink-0 text-xs muted">{u.completed}/{u.total}</span>
            </div>
            <ul className="space-y-1">
              {u.topics.map((t) => (
                <li key={t.topic} className="flex items-center justify-between gap-2 text-sm">
                  <span className="min-w-0 truncate text-ink-soft">{t.topic}</span>
                  <select value={t.status} onChange={(e) => set(u.unit, t.topic, e.target.value as TopicStatus)}
                    className={`shrink-0 cursor-pointer rounded-full border-0 px-2 py-0.5 text-xs font-medium focus:ring-2 focus:ring-lav-200 ${STATUS_STYLE[t.status]}`}>
                    {STATUSES.map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
                  </select>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function AnalysisTab({ subject }: { subject: SubjectFull }) {
  const C = palette(useTheme().resolved === "dark");
  const { data, loading, error } = useAsync(() => api.analysis(subject.id), [subject.id]);
  if (error) return <Notice tone="warn">{error}</Notice>;
  if (loading && !data) return <div className="grid gap-4 lg:grid-cols-2">{[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-72" />)}</div>;
  if (!data) return null;

  if (data.totals.papers === 0) {
    return (
      <div className="space-y-5">
        <Empty icon={<BarChart3 className="h-5 w-5" />} title="No papers analysed yet">Upload previous papers to see unit and topic trends.</Empty>
        <Tracker subject={subject} />
      </div>
    );
  }

  const unitData = data.units.map((u) => ({ name: `U${u.unit}`, title: u.title, Questions: u.questions, CAT1: u.CAT1, CAT2: u.CAT2, SEMESTER: u.SEMESTER }));
  const sorted = [...data.units].sort((a, b) => b.questions - a.questions);
  const marksData = Object.entries(data.marks_by_type).flatMap(([et, m]) => Object.entries(m).map(([k, v]) => ({ et, k, v })));
  const markKeys = Array.from(new Set(marksData.map((x) => x.k))).sort((a, b) => Number(a) - Number(b));
  const marksRows = ["CAT1", "CAT2", "SEMESTER"].filter((et) => data.marks_by_type[et]).map((et) => {
    const row: Record<string, string | number> = { name: EXAM_LABEL[et] };
    markKeys.forEach((k) => { row[`${k} marks`] = data.marks_by_type[et][k] || 0; });
    return row;
  });
  const qtypeData = data.qtypes.map((q) => ({ name: QTYPE_LABEL[q.qtype] || q.qtype, value: q.count }));

  return (
    <div className="space-y-5">
      {data.confidence.level === "low" && <Notice tone="warn">{data.confidence.message}</Notice>}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Papers analysed" value={data.totals.papers} hint={`${data.totals.questions} questions`} />
        <Stat label="Distinct concepts" value={data.totals.concepts} hint={`${data.totals.repeated_concepts} asked more than once`} />
        <Stat label="Syllabus topics asked" value={data.totals.syllabus_topics ? `${data.totals.topics_asked}/${data.totals.syllabus_topics}` : "—"} hint="at least once" />
        <Stat label="Most tested unit" value={sorted[0]?.questions ? `Unit ${sorted[0].unit}` : "—"} hint={sorted.length > 1 && sorted[sorted.length - 1] ? `Least: Unit ${sorted[sorted.length - 1].unit}` : undefined} />
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <ChartCard title="Questions per unit" hint={data.unassigned_unit ? `${data.unassigned_unit} questions couldn't be mapped to a unit — fix them in Questions.` : "All past questions, every exam type."}>
          <ResponsiveContainer><BarChart data={unitData} margin={{ left: -20, right: 8 }}>
            <CartesianGrid vertical={false} stroke="#f0ede6" /><XAxis dataKey="name" tick={axis} axisLine={false} tickLine={false} /><YAxis tick={axis} axisLine={false} tickLine={false} allowDecimals={false} />
            <Tooltip cursor={{ fill: "#f5f3ff" }} labelFormatter={(l, p) => `${l} · ${p?.[0]?.payload?.title || ""}`} />
            <RBar dataKey="Questions" fill="#8b7cf6" radius={[6, 6, 0, 0]} />
          </BarChart></ResponsiveContainer>
        </ChartCard>

        <ChartCard title="CAT vs semester, by unit" hint="How each exam type spreads its questions.">
          <ResponsiveContainer><BarChart data={unitData} margin={{ left: -20, right: 8 }}>
            <CartesianGrid vertical={false} stroke="#f0ede6" /><XAxis dataKey="name" tick={axis} axisLine={false} tickLine={false} /><YAxis tick={axis} axisLine={false} tickLine={false} allowDecimals={false} />
            <Tooltip cursor={{ fill: "#f5f3ff" }} /><Legend iconType="circle" wrapperStyle={{ fontSize: 11 }} formatter={(v) => EXAM_LABEL[v] || v} />
            {(["CAT1", "CAT2", "SEMESTER"] as const).map((k, i, arr) => <RBar key={k} dataKey={k} stackId="a" fill={C[k]} radius={i === arr.length - 1 ? [6, 6, 0, 0] : undefined} />)}
          </BarChart></ResponsiveContainer>
        </ChartCard>

        <ChartCard title="2-mark vs long-answer distribution" hint="Question slots per exam type.">
          <ResponsiveContainer><BarChart data={marksRows} margin={{ left: -20, right: 8 }}>
            <CartesianGrid vertical={false} stroke="#f0ede6" /><XAxis dataKey="name" tick={axis} axisLine={false} tickLine={false} /><YAxis tick={axis} axisLine={false} tickLine={false} allowDecimals={false} />
            <Tooltip cursor={{ fill: "#f5f3ff" }} /><Legend iconType="circle" wrapperStyle={{ fontSize: 11 }} />
            {markKeys.map((k, i) => <RBar key={k} dataKey={`${k} marks`} fill={PIE[i % PIE.length]} radius={[4, 4, 0, 0]} />)}
          </BarChart></ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Question types" hint="Detected from wording (explain, draw, derive, calculate…).">
          <ResponsiveContainer><PieChart>
            <Pie data={qtypeData} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={2} stroke="none">
              {qtypeData.map((_, i) => <Cell key={i} fill={PIE[i % PIE.length]} />)}
            </Pie>
            <Tooltip /><Legend iconType="circle" layout="vertical" align="right" verticalAlign="middle" wrapperStyle={{ fontSize: 11 }} />
          </PieChart></ResponsiveContainer>
        </ChartCard>

        {data.by_year.length > 1 && (
          <ChartCard title="Questions by year" hint="Uploaded papers per year and exam type.">
            <ResponsiveContainer><LineChart data={data.by_year} margin={{ left: -20, right: 8 }}>
              <CartesianGrid vertical={false} stroke="#f0ede6" /><XAxis dataKey="year" tick={axis} axisLine={false} tickLine={false} /><YAxis tick={axis} axisLine={false} tickLine={false} allowDecimals={false} />
              <Tooltip /><Legend iconType="circle" wrapperStyle={{ fontSize: 11 }} formatter={(v) => EXAM_LABEL[v] || v} />
              {(["CAT1", "CAT2", "SEMESTER"] as const).map((k) => <Line key={k} type="monotone" dataKey={k} stroke={C[k]} strokeWidth={2} dot={{ r: 3 }} />)}
            </LineChart></ResponsiveContainer>
          </ChartCard>
        )}

        <div className="card p-5">
          <h3 className="font-semibold">Unit-wise prediction priority</h3>
          <p className="mb-3 text-xs muted">Average of each unit's top semester predictions.</p>
          <div className="space-y-2.5">
            {data.unit_priority.map((u) => {
              const t = data.units.find((x) => x.unit === u.unit);
              return (
                <div key={u.unit} className="grid grid-cols-[minmax(0,1fr)_90px] items-center gap-3 sm:grid-cols-[minmax(0,1fr)_140px_90px]">
                  <span className="truncate text-sm">Unit {u.unit}{t?.title ? ` · ${t.title}` : ""}</span>
                  <div className="hidden sm:block"><div className="h-2 rounded-full bg-stone-100"><div className="h-full rounded-full" style={{ width: `${u.score}%`, background: PRIORITY_HEX[u.priority] }} /></div></div>
                  <div className="text-right"><PriorityPill p={u.priority} /></div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <div className="card p-5">
          <h3 className="font-semibold">Most repeated topics</h3>
          <p className="mb-3 text-xs muted">Concepts grouped across wordings, ranked by papers they appeared in.</p>
          <ul className="space-y-2">
            {data.top_topics.slice(0, 10).map((t, i) => (
              <li key={i} className="flex items-center gap-3">
                <span className="w-5 shrink-0 text-right text-xs muted">{i + 1}</span>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm" title={t.example}>{t.label}</div>
                  <div className="text-xs muted">{t.unit ? `Unit ${t.unit} · ` : ""}{t.cat} CAT · {t.semester} semester</div>
                </div>
                <span className="chip shrink-0 bg-lav-50 text-lav-700">{t.papers} papers</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="card p-5">
          <h3 className="font-semibold">Syllabus topics never asked</h3>
          <p className="mb-3 text-xs muted">Not seen in any uploaded paper — lower priority, but don't ignore them.</p>
          {data.untested_topics.length === 0 ? <p className="text-sm muted">{data.totals.syllabus_topics ? "Every syllabus topic has appeared at least once." : "Add the syllabus to see this."}</p> : (
            <div className="flex flex-wrap gap-1.5">
              {data.untested_topics.map((t, i) => <span key={i} className="chip bg-stone-100 text-ink-soft">U{t.unit} · {t.topic}</span>)}
            </div>
          )}
        </div>
      </div>

      <Tracker subject={subject} />
    </div>
  );
}
