import { useCallback, useEffect, useRef, useState, type Dispatch, type SetStateAction } from 'react';
import type { TvAutoSyncSessionResponse } from '../types/quickset';
import { getSession } from '../services/quicksetService';

interface SessionPollingResult {
  data: TvAutoSyncSessionResponse | null;
  error: string | null;
  setData: Dispatch<SetStateAction<TvAutoSyncSessionResponse | null>>;
}

const POLL_INTERVAL_MS = 2000;

export function useSessionPolling(sessionId: string | null, apiKey: string | null): SessionPollingResult {
  const [data, setData] = useState<TvAutoSyncSessionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<number | null>(null);
  const completedRef = useRef(false);
  const generationRef = useRef(0);
  const activeControllerRef = useRef<AbortController | null>(null);

  const clearTimer = () => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  };

  const abortInFlight = () => {
    if (activeControllerRef.current) {
      activeControllerRef.current.abort();
      activeControllerRef.current = null;
    }
  };

  const isComplete = (payload: TvAutoSyncSessionResponse | null): boolean => {
    if (!payload) {
      return false;
    }
    const finished = Boolean(payload.session.finished_at);
    return finished && payload.session.analyzer_ready === true;
  };

  useEffect(() => {
    generationRef.current += 1;
    const currentGeneration = generationRef.current;
    let cancelled = false;
    abortInFlight();
    clearTimer();
    completedRef.current = false;

    if (!sessionId || !apiKey) {
      setData(null);
      setError(null);
      completedRef.current = false;
      return () => {
        cancelled = true;
      };
    }

    const poll = async () => {
      const controller = new AbortController();
      activeControllerRef.current = controller;
      try {
        const response = await getSession(sessionId, apiKey, controller.signal);
        if (cancelled || currentGeneration !== generationRef.current) {
          return;
        }
        setData(response);
        setError(null);
        if (isComplete(response)) {
          completedRef.current = true;
          clearTimer();
          return;
        }
      } catch (err) {
        if (cancelled || controller.signal.aborted || currentGeneration !== generationRef.current) {
          return;
        }
        const message = err instanceof Error ? err.message : 'Failed to fetch session';
        setError(message);
      } finally {
        if (!cancelled && !completedRef.current && currentGeneration === generationRef.current) {
          clearTimer();
          timerRef.current = window.setTimeout(poll, POLL_INTERVAL_MS);
        }
      }
    };

    poll();

    return () => {
      cancelled = true;
      abortInFlight();
      clearTimer();
      completedRef.current = false;
    };
  }, [sessionId, apiKey]);

  const replaceData = useCallback<Dispatch<SetStateAction<TvAutoSyncSessionResponse | null>>>(
    (next) => {
      setData((prev) => {
        const resolved = typeof next === 'function'
          ? (next as (value: TvAutoSyncSessionResponse | null) => TvAutoSyncSessionResponse | null)(prev)
          : next;
        if (isComplete(resolved)) {
          completedRef.current = true;
          clearTimer();
        }
        return resolved;
      });
    },
    []
  );

  return { data, error, setData: replaceData };
}
