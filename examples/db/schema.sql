-- examples/db/schema.sql

CREATE TABLE projects (
  id TEXT PRIMARY KEY,
  name TEXT,
  credit_balance NUMERIC(18,6) DEFAULT 0
);

CREATE TABLE usage_records (
  id TEXT PRIMARY KEY,
  project_id TEXT,
  ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  provider TEXT,
  model TEXT,
  prompt_tokens INTEGER,
  completion_tokens INTEGER,
  estimated_cost NUMERIC(18,6),
  provider_request_id TEXT,
  is_estimated BOOLEAN DEFAULT TRUE
);
