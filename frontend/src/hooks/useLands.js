/**
 * hooks/useLands.js — Shared lands list data (web + RN ready)
 */

import { useState, useEffect, useCallback } from "react";
import { listLands } from "../services/api";

export function useLands({ autoFetch = true } = {}) {
  const [lands, setLands] = useState([]);
  const [loading, setLoading] = useState(autoFetch);
  const [error, setError] = useState(null);

  const refetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listLands();
      setLands(res.lands || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (autoFetch) refetch();
  }, [autoFetch, refetch]);

  return { lands, setLands, loading, error, refetch };
}