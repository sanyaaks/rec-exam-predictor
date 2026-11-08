// Light / dark / system theme, remembered per browser. The initial class is set by an inline
// script in index.html (before React loads) so there is no flash of the wrong theme.
import { useEffect, useState } from "react";

export type ThemePref = "light" | "dark" | "system";
const KEY = "rec-theme";
const EVENT = "rec-theme-change";
const media = () => window.matchMedia("(prefers-color-scheme: dark)");

export function getPref(): ThemePref {
  try {
    const v = localStorage.getItem(KEY);
    if (v === "light" || v === "dark" || v === "system") return v;
  } catch { /* storage blocked */ }
  return "system";
}

export function resolve(pref: ThemePref): "light" | "dark" {
  return pref === "system" ? (media().matches ? "dark" : "light") : pref;
}

export function apply(pref: ThemePref) {
  document.documentElement.classList.toggle("dark", resolve(pref) === "dark");
}

export function useTheme() {
  const [pref, setPrefState] = useState<ThemePref>(getPref);
  useEffect(() => {
    // keep every toggle on the page (sidebar, mobile bar) in sync
    const sync = () => setPrefState(getPref());
    window.addEventListener(EVENT, sync);
    return () => window.removeEventListener(EVENT, sync);
  }, []);
  useEffect(() => {
    apply(pref);
    if (pref !== "system") return;
    const m = media();
    const onChange = () => apply("system");
    m.addEventListener("change", onChange);
    return () => m.removeEventListener("change", onChange);
  }, [pref]);
  const setPref = (p: ThemePref) => {
    try { localStorage.setItem(KEY, p); } catch { /* storage blocked */ }
    setPrefState(p);
    window.dispatchEvent(new Event(EVENT));
  };
  return { pref, resolved: resolve(pref), setPref };
}
