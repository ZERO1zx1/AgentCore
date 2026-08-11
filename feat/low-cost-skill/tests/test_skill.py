import json
import hashlib
import sqlite3
import pytest

from feat.low-cost-skill.skill_low_cost import low_cost_request, low_cost_request_sync

# We'll monkeypatch call_provider inside the module to avoid real HTTP calls
import importlib

module = importlib.import_module('feat.low-cost-skill.skill_low_cost')

class DummyResp:
    def __init__(self, text, usage=None, id=None):
        self._d = {"text": text, "usage": usage or {}, "id": id}
    def json(self):
        return self._d

async def fake_call_provider_success(model, prompt, max_tokens=128):
    # cheap model returns short unhelpful text, forcing escalation
    if "cheap" in model:
        return {"text": "I don't know.", "usage": {"prompt_tokens": 3, "completion_tokens": 2}, "id": "r1"}
    return {"text": "Detailed answer from expensive model.", "usage": {"prompt_tokens": 3, "completion_tokens": 20}, "id": "r2"}

@pytest.fixture(autouse=True)
def patch_provider(monkeypatch, tmp_path):
    # ensure DB in a temp location
    tmp_db = tmp_path / "test.db"
    monkeypatch.setenv('CREDIT_DB_PATH', str(tmp_db))
    # re-import/init module to pick up env
    import importlib
    importlib.reload(module)
    monkeypatch.setattr(module, 'call_provider', fake_call_provider_success)
    yield

@pytest.mark.asyncio
async def test_low_cost_escalates_and_records():
    res = await module.low_cost_request('proj-test', 'Explain X in detail')
    assert res['model'] == module.EXP_MODEL
    assert 'Detailed answer' in res['response']
    # Check sqlite record created
    conn = sqlite3.connect(module.DB)
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM usage_records')
    cnt = cur.fetchone()[0]
    conn.close()
    assert cnt >= 1
