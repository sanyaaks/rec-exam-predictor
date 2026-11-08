import { DependencyList, useCallback, useEffect, useRef, useState } from "react";
import { api, Meta } from "../api";

export function useAsync<T>(fn: () => Promise<T>, deps: DependencyList) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const seq = useRef(0);
  const run = useCallback(async (silent = false) => {
    const my = ++seq.current;
    if (!silent) setLoading(true);
    setError(null);
    try {
      const d = await fn();
      if (my === seq.current) setData(d);
    } catch (e) {
      if (my === seq.current) setError(e instanceof Error ? e.message : String(e));
    } finally {
      if (my === seq.current) setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => { run(); }, [run]);
  return { data, setData, error, loading, reload: run };
}

let metaCache: Promise<Meta> | null = null;
export function useMeta() {
  const [meta, setMeta] = useState<Meta | null>(null);
  useEffect(() => {
    metaCache = metaCache || api.meta();
    metaCache.then(setMeta).catch(() => { metaCache = null; });
  }, []);
  return meta;
}
