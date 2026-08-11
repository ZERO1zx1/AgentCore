from fastapi import FastAPI, HTTPException
import os
import sqlite3
from pydantic import BaseModel

# Simple balance and policy endpoints for demo (sqlite-backed)
DB_PATH = os.getenv('CREDIT_DB_PATH', 'credit_demo.db')

app = FastAPI()

# Init tables if missing
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, name TEXT, credit_balance TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS policies (project_id TEXT PRIMARY KEY, alert_low TEXT, auto_degrade TEXT, block_threshold TEXT)''')
    conn.commit()
    conn.close()

init_db()

class PolicyIn(BaseModel):
    alert_low: str = None
    auto_degrade: str = None
    block_threshold: str = None

@app.get('/api/projects/{project_id}/balance')
def get_balance(project_id: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT credit_balance FROM projects WHERE id=?', (project_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail='project not found')
    return {'balance': row[0], 'currency': 'USD'}

@app.post('/api/projects/{project_id}/policy')
def set_policy(project_id: str, policy: PolicyIn):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # upsert
    cur.execute('INSERT OR REPLACE INTO policies (project_id, alert_low, auto_degrade, block_threshold) VALUES (?, ?, ?, ?)',
                (project_id, policy.alert_low, policy.auto_degrade, policy.block_threshold))
    conn.commit()
    conn.close()
    return {'ok': True}

@app.get('/api/projects/{project_id}/policy')
def get_policy(project_id: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT alert_low, auto_degrade, block_threshold FROM policies WHERE project_id=?', (project_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return {'policy': None}
    return {'policy': {'alert_low': row[0], 'auto_degrade': row[1], 'block_threshold': row[2]}}
