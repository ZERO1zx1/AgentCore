// examples/frontend/CreditBadge.jsx
import React, { useEffect, useState } from 'react';

export default function CreditBadge({ projectId }) {
  const [balance, setBalance] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    async function fetchBalance() {
      setLoading(true);
      try {
        const res = await fetch(`/api/projects/${projectId}/balance`);
        if (!res.ok) throw new Error('Failed');
        const data = await res.json();
        if (mounted) setBalance(data.balance);
      } catch (e) {
        console.error(e);
      } finally {
        if (mounted) setLoading(false);
      }
    }
    fetchBalance();
    const iv = setInterval(fetchBalance, 60000); // refresh every minute
    return () => { mounted = false; clearInterval(iv); };
  }, [projectId]);

  if (loading) return <span className="credit-badge">Loading…</span>;
  if (balance == null) return <span className="credit-badge">—</span>;
  const low = parseFloat(balance) < 1.0;
  return <span className={`credit-badge ${low ? 'low' : ''}`}>Balance: {balance}</span>;
}
