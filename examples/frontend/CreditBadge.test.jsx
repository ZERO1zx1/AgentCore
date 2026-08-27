// examples/frontend/CreditBadge.test.jsx
import React from 'react';
import { render, act } from '@testing-library/react';
import CreditBadge from './CreditBadge.jsx';

beforeEach(() => {
  jest.useFakeTimers();
  global.fetch = jest.fn(() =>
    Promise.resolve({ ok: true, json: () => Promise.resolve({ balance: '9.5' }) })
  );
});
afterEach(() => {
  jest.useRealTimers();
  global.fetch = jest.fn();
});

test('multiple polling cycles send only GET and never a POST', async () => {
  render(<CreditBadge projectId="p1" intervalMs={1000} />);
  await act(async () => {
    await Promise.resolve();
  }); // initial fetch resolves
  await act(async () => {
    jest.advanceTimersByTime(1000);
    await Promise.resolve();
  }); // 1st interval poll
  await act(async () => {
    jest.advanceTimersByTime(1000);
    await Promise.resolve();
  }); // 2nd interval poll
  const calls = global.fetch.mock.calls;
  expect(calls.length).toBeGreaterThanOrEqual(3);
  for (const [url, opts] of calls) {
    expect(opts && opts.method).not.toBe('POST');
    expect(url).toContain('/api/projects/');
  }
});

test('unmount clears the interval (no fetches after unmount)', async () => {
  const { unmount } = render(<CreditBadge projectId="p1" intervalMs={1000} />);
  await act(async () => {
    await Promise.resolve();
  });
  const before = global.fetch.mock.calls.length;
  unmount();
  await act(async () => {
    jest.advanceTimersByTime(5000);
    await Promise.resolve();
  });
  expect(global.fetch.mock.calls.length).toBe(before);
});

test('late provider response after unmount does not update state', async () => {
  let resolveFn;
  global.fetch = jest.fn(
    () =>
      new Promise((resolve) => {
        resolveFn = () =>
          resolve({ ok: true, json: () => Promise.resolve({ balance: '7.0' }) });
      })
  );
  const { unmount, container } = render(
    <CreditBadge projectId="p1" intervalMs={100000} />
  );
  await act(async () => {
    await Promise.resolve();
  });
  unmount();
  await act(async () => {
    resolveFn();
    await Promise.resolve();
  });
  expect(container.textContent).not.toContain('7.0');
});
