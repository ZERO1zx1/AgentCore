// examples/frontend/App.test.jsx
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import App from './App.jsx';

const bal = () => Promise.resolve({ ok: true, json: () => Promise.resolve({ balance: '9.5' }) });

beforeEach(() => {
  global.fetch = jest.fn((url, opts) => {
    if (url.includes('/balance')) return bal();
    return Promise.resolve({
      ok: true,
      json: () =>
        Promise.resolve({
          usage: {
            estimated_cost: '0.0001',
            actual_cost: null,
            cost_source: 'estimate',
            new_balance: '9.49',
          },
        }),
    });
  });
});

test('rapid double-click causes exactly one POST', async () => {
  render(<App />);
  const btn = screen.getByText(/Run request/i);
  fireEvent.click(btn);
  fireEvent.click(btn);
  await waitFor(() =>
    expect(
      global.fetch.mock.calls.filter(([u, o]) => o && o.method === 'POST').length
    ).toBe(1)
  );
});

test('successful POST triggers a new balance GET', async () => {
  render(<App />);
  fireEvent.click(screen.getByText(/Run request/i));
  await waitFor(() => {
    const posts = global.fetch.mock.calls.filter(([u, o]) => o && o.method === 'POST');
    expect(posts.length).toBe(1);
    const balances = global.fetch.mock.calls.filter(([u]) => u.includes('/api/projects/'));
    expect(balances.length).toBeGreaterThanOrEqual(2);
  });
});

test('estimated vs provider-confirmed cost labels', async () => {
  global.fetch = jest.fn((url, opts) => {
    if (url.includes('/balance')) return bal();
    return Promise.resolve({
      ok: true,
      json: () =>
        Promise.resolve({
          usage: {
            estimated_cost: '0.0001',
            actual_cost: '0.005',
            cost_source: 'provider',
            new_balance: '9.495',
          },
        }),
    });
  });
  render(<App />);
  fireEvent.click(screen.getByText(/Run request/i));
  await waitFor(() =>
    expect(screen.getByText(/Provider-confirmed cost: 0\.005/)).toBeInTheDocument()
  );

  global.fetch = jest.fn((url, opts) => {
    if (url.includes('/balance')) return bal();
    return Promise.resolve({
      ok: true,
      json: () =>
        Promise.resolve({
          usage: {
            estimated_cost: '0.0002',
            actual_cost: null,
            cost_source: 'estimate',
            new_balance: '9.498',
          },
        }),
    });
  });
  fireEvent.click(screen.getByText(/Run request/i));
  await waitFor(() =>
    expect(screen.getByText(/Estimated cost: 0\.0002 \(estimate\)/)).toBeInTheDocument()
  );
});
