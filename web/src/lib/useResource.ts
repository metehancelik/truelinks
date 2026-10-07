"use client";

import { useCallback, useEffect, useState } from "react";
import { errorMessage } from "./api";

const POLL_MS = 3000;

/**
 * Loads a resource and keeps it fresh. The agents work in the background for
 * a minute or two, so the page polls instead of waiting on one long request.
 */
export function useResource<T>(load: () => Promise<T>) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setData(await load());
      setError(null);
    } catch (problem) {
      setError(errorMessage(problem));
    }
  }, [load]);

  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;

    const tick = async () => {
      await refresh();
      if (!stopped) timer = setTimeout(tick, POLL_MS);
    };
    tick();

    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [refresh]);

  return { data, error, refresh };
}
