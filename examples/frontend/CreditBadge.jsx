// examples/frontend/CreditBadge.jsx
// Read-only balance display. Polls GET /api/projects/{projectId}/balance only.
// It NEVER sends a POST /api/agent/request — that is the caller's (parent's)
// responsibility, triggered by an explicit user action. This keeps the badge
// from spending credit on its own, in line with credit-safe-agent principles.
import React, { useEffect, useRef, useState } from 'react';

export default function CreditBadge({ projectId, refreshNonce = 0, intervalMs = 60000 }) {
  const [balance, setBalance] = useState(null);
  const [error, setError] = useState(null);
  const inFlight = useRef(false);
  const cancelled = useRef(false);

  useEffect(() => {
    cancelled.current = false;
    const ac = new AbortController();

    async function loadBalance() {
      if (!projectId || inFlight.current) return;
      inFlight.current = true;
      try {
        const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/balance`, {
          signal: ac.signal,
        });
        if (cancelled.current) return;
        if (!res.ok) throw new Error(`balance request failed (${res.status})`);
        const data = await res.json();
        if (cancelled.current) return;
        setBalance(data.balance);
        setError(null);
      } catch (e) {
        if (cancelled.current || e.name === 'AbortError') return;
        setError(e.message);
      } finally {
        inFlight.current = false;
      }
    }

    loadBalance();
    const iv = setInterval(loadBalance, intervalMs);
    return () => {
      cancelled.current = true;
      ac.abort();
      clearInterval(iv);
    };
  }, [projectId, intervalMs, refreshNonce]);

  if (error) return <span className="credit-badge error" title={error}>Error</span>;
  if (balance == null) return <span className="credit-badge">Loading…</span>;
  const low = parseFloat(balance) < 1.0;
  return (
    <span className={`credit-badge ${low ? 'low' : ''}`}>
      Balance: {balance}
    </span>
  );
}
