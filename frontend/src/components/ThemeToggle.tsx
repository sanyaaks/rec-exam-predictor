import { Monitor, Moon, Sun } from "lucide-react";
import { ThemePref, useTheme } from "../lib/theme";

const OPTIONS: { value: ThemePref; label: string; Icon: typeof Sun }[] = [
  { value: "light", label: "Light", Icon: Sun },
  { value: "dark", label: "Dark", Icon: Moon },
  { value: "system", label: "System", Icon: Monitor },
];

/** Segmented Light / Dark / System switch. `compact` shows a single icon button that cycles. */
export default function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const { pref, resolved, setPref } = useTheme();
  if (compact) {
    const next: ThemePref = resolved === "dark" ? "light" : "dark";
    const Icon = resolved === "dark" ? Sun : Moon;
    return (
      <button type="button" onClick={() => setPref(next)} className="btn-ghost h-9 w-9 !px-0"
        aria-label={`Switch to ${next} theme`} title={`Switch to ${next} theme`}>
        <Icon className="h-4 w-4" />
      </button>
    );
  }
  return (
    <div role="radiogroup" aria-label="Theme" className="flex rounded-xl border border-line bg-surface p-0.5">
      {OPTIONS.map(({ value, label, Icon }) => (
        <button key={value} type="button" role="radio" aria-checked={pref === value} onClick={() => setPref(value)}
          title={`${label} theme`}
          className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg px-2 py-1.5 text-xs font-medium transition ${
            pref === value ? "bg-lav-100 text-lav-700" : "text-ink-mute hover:text-ink"}`}>
          <Icon className="h-3.5 w-3.5" />{label}
        </button>
      ))}
    </div>
  );
}
