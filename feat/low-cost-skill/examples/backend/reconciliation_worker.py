"""Reconciliation worker (demo)

- Periodically fetches provider billing/usage report from PROVIDER_BILLING_URL (a JSON endpoint or local file URL)
- Matches provider_request_id to local usage_records and adjusts project balances
- Creates an 'adjustments' table entries in DB when differences found
- Sends alerts via alerts.send_alert when discrepancies exceed threshold

Note: Replace provider fetching and auth with real provider API client in production.
"""
import os
import sqlite3
import time
import json
import requests
from decimal import Decimal

DB = os.getenv('CREDIT_DB_PATH', 'credit_demo.db')
PROVIDER_BILLING_URL = os.getenv('PROVIDER_BILLING_URL', '')  # e.g. https://provider.example.com/billing/recent
ALERT_THRESHOLD = Decimal(os.getenv('RECONCILE_ALERT_THRESHOLD', '0.01'))

# simple alerts helper (uses env ALERT_WEBHOOK_URL)
import alerts


def init():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS adjustments (id TEXT PRIMARY KEY, usage_id TEXT, billed_amount TEXT, recorded_amount TEXT, ts TEXT DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()


def fetch_provider_rows():
    # For demo: support file:// path or HTTP(S)
    if PROVIDER_BILLING_URL.startswith('file://'):
        path = PROVIDER_BILLING_URL[len('file://'):]
        with open(path, 'r') as f:
            data = json.load(f)
        return data
    if not PROVIDER_BILLING_URL:
        print('No PROVIDER_BILLING_URL configured; skipping')
        return []
    resp = requests.get(PROVIDER_BILLING_URL, timeout=30)
    resp.raise_for_status()
    return resp.json()


def reconcile_once():
    rows = fetch_provider_rows()
    if not rows:
        return
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    for r in rows:
        provider_req_id = r.get('provider_request_id')
        billed = Decimal(str(r.get('billed_amount', '0')))
        # find local usage
        cur.execute('SELECT id, project_id, estimated_cost FROM usage_records WHERE provider_request_id=?', (provider_req_id,))
        hit = cur.fetchone()
        if hit:
            usage_id, project_id, recorded = hit
            recorded_amount = Decimal(str(recorded))
            if billed != recorded_amount:
                # create adjustment and update project balance
                adj_id = provider_req_id
                cur.execute('INSERT OR REPLACE INTO adjustments (id, usage_id, billed_amount, recorded_amount) VALUES (?, ?, ?, ?)',
                            (adj_id, usage_id, str(billed), str(recorded_amount)))
                # difference = billed - recorded; we subtract the difference (provider charged more -> reduce balance)
                diff = billed - recorded_amount
                cur.execute('SELECT credit_balance FROM projects WHERE id=?', (project_id,))
                pr = cur.fetchone()
                if pr:
                    new_bal = Decimal(str(pr[0])) - diff
                    cur.execute('UPDATE projects SET credit_balance=? WHERE id=?', (str(new_bal), project_id))
                    conn.commit()
                    # alert if difference big
                    if abs(diff) >= ALERT_THRESHOLD:
                        alerts.send_alert(project_id, f'Reconciliation adjustment for request {provider_req_id}: billed {billed} vs recorded {recorded_amount}, diff {diff}, new_balance {new_bal}')
        else:
            # Orphan billed row: insert a usage_record or notify admin
            alerts.send_alert('admin', f'Orphan billing row from provider: {r}')
    conn.close()


if __name__ == '__main__':
    init()
    while True:
        try:
            reconcile_once()
        except Exception as e:
            print('Reconcile error:', e)
        time.sleep(int(os.getenv('RECONCILE_INTERVAL_SEC', '300')))
