<<<<<<< HEAD
# AI-Based Overtime Verification System - Phase 1

This is the standalone Phase 1 implementation from the proposal:

- `backend_engine.py` - shared backend, SQLite storage, document extraction, risk scoring, Groq hook, and Excel export.
- `worker_portal.py` - Streamlit portal for employees/workers to submit overtime claims.
- `supervisor_portal.py` - Streamlit portal for supervisors to review, re-analyze, approve, reject, or escalate claims.

## Setup

```powershell
python -m pip install -r requirements.txt
```

For Groq free-tier AI summaries, set your API key before launching:

```powershell
$env:GROQ_API_KEY="your_groq_api_key"
```

If no Groq key is set, the system still works using the local electrical-industry rules engine.

## Run

Open the worker portal:

```powershell
streamlit run worker_portal.py --server.port 8501
```

Open the supervisor portal in another terminal:

```powershell
streamlit run supervisor_portal.py --server.port 8502
```

The apps store data in `data/overtime_phase1.sqlite3` and reports in `data/reports`.
=======
# Overtime_Control
AI-Based Overtime Verification System for electrical operations. Built with Streamlit and Python, it provides worker and supervisor portals, verifies attendance-based overtime, deducts lunch breaks, analyzes work complexity, flags unusual claims, supports Groq AI summaries, and exports management-ready Excel reports.
>>>>>>> 0e2450234f080ba400485b84989dedebfd26d6c9
