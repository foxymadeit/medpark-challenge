import { useCallback, useEffect, useState } from "react";
export function useData<T>(loader: () => Promise<T>, interval = 1500) {
  const [data, setData] = useState<T>();
  const [error, setError] = useState("");
  const [version, setVersion] = useState(0);
  const refresh = useCallback(() => setVersion((v) => v + 1), []);
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      try {
        const result = await loader();
        if (active) {
          setData(result);
          setError("");
        }
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : "requestFailed");
      } finally {
        if (active && interval) timer = setTimeout(load, interval);
      }
    }
    void load();
    const update = () => {
      clearTimeout(timer);
      void load();
    };
    window.addEventListener("sm-update", update);
    return () => {
      active = false;
      clearTimeout(timer);
      window.removeEventListener("sm-update", update);
    };
  }, [loader, interval, version]);
  return { data, error, refresh };
}
export function notifyUpdate() {
  window.dispatchEvent(new Event("sm-update"));
}
