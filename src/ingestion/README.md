# Ingestion (`src/ingestion/`)

Input routing and normalization before planning.

- `router.py` — routes input to the right handler.
- `repository.py` — repository inspection.
- `text.py`, `structured.py`, `pdf.py`, `assets.py` — input type handlers.

Media is delivered as verified path attachments, never as binary/base64 in
prompts.
