// examples/frontend/App.jsx
import React, { useState, useRef } from 'react';
import CreditBadge from './CreditBadge.jsx';

const DEFAULT_MODEL = 'gpt-3.5-cheap';

export default function App() {
  const [projectId, setProjectId] = useState('demo-project');
  const [prompt, setPrompt] = useState('Tell me about AgentCore.');
  const [balanceRefresh, setBalanceRefresh] = useState(0);
  const [costInfo, setCostInfo] = useState(null); // { estimated_cost, actual_cost, cost_source }
  const [runError, setRunError] = useState(null);
  const runningRef = useRef(false); // immediate in-flight guard (useRef)
  const [running, setRunning] = useState(false);

  // Explicit, user-triggered AI request — the ONLY place a POST happens.
  async function runRequest() {
    if (runningRef.current) return; // ignore re-entrant calls
    runningRef.current = true;
    setRunning(true);
    setRunError(null);
    try {
      const res = await fetch('/api/agent/request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_id: projectId, prompt, model: DEFAULT_MODEL }),
      });
      if (!res.ok) throw new Error(`request failed (${res.status})`);
      const data = await res.json();
      setCostInfo({
        estimated_cost: data.usage?.estimated_cost ?? null,
        actual_cost: data.usage?.actual_cost ?? null,
        cost_source: data.usage?.cost_source ?? 'estimate',
      });
      // Refresh the read-only balance badge after the explicit request.
      setBalanceRefresh((n) => n + 1);
    } catch (e) {
      setRunError(e.message);
    } finally {
      runningRef.current = false;
      setRunning(false);
    }
  }

  return (
    <main style={{ fontFamily: 'sans-serif', padding: 24 }}>
      <h1>AgentCore Credit Badge</h1>
      <label>
        Project ID
        <input value={projectId} onChange={(e) => setProjectId(e.target.value)} />
      </label>
      <label style={{ display: 'block', marginTop: 8 }}>
        Prompt
        <input value={prompt} onChange={(e) => setPrompt(e.target.value)} style={{ width: 320 }} />
      </label>
      <p>
        <button type="button" onClick={runRequest} disabled={running}>
          {running ? 'Running…' : 'Run request'}
        </button>{' '}
        <CreditBadge projectId={projectId} refreshNonce={balanceRefresh} />
      </p>
      {costInfo && costInfo.actual_cost != null && (
        <p>Provider-confirmed cost: {costInfo.actual_cost}</p>
      )}
      {costInfo && costInfo.actual_cost == null && (
        <p>Estimated cost: {costInfo.estimated_cost} (estimate)</p>
      )}
      {runError && <p style={{ color: 'crimson' }}>{runError}</p>}
      <p style={{ color: '#666', fontSize: 12 }}>
        Requires the backend proxy running on the same origin with a seeded
        <code> projects </code> row for the project ID.
      </p>
    </main>
  );
}
