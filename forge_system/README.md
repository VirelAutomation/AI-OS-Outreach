# FORGE System

This project has one canonical backend and one legacy prototype.

## Canonical backend
- Root launcher: `backend.py`
- Modular app: `forge_system/`
- Entry app object: `forge_system/main.py`
- Database schema: `forge_system/migrations/`
- Config source: `.env` in this folder

Run the backend from this folder:

```powershell
python backend.py
```

Or:

```powershell
uvicorn backend:app --reload --port 8000
```

## Legacy artifacts
- `dashboard.html` is a static prototype / reference frontend, not the canonical product shell.
- `legacy/backend_single_file_legacy.py` is the old monolithic backend retained only as backup.

## Credential handling
- Put runtime secrets in `.env`.
- Put OAuth / service-account JSON files in `..\credentials\`.
- Do not keep credential JSON files in the project root.

## Current backend focus
This backend is structured around:
- outreach
- jarvis orchestration
- automations
- landing-page signals
- Supabase + Redis infrastructure
- SCI runtime for target-state planning, founder allocation, approvals, execution traces, and HF eval summaries

## SCI operator APIs
- `POST /api/jarvis/objectives` runs the SCI loop and persists the latest world-state and objective graph.
- `GET /api/jarvis/world-state` returns the latest founder/company world-state snapshot.
- `GET /api/jarvis/allocations`, `/approvals`, `/executions`, and `/evals` expose the operator-facing SCI surfaces consumed by `forge-os`.
