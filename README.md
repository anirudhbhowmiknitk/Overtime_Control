# Overtime Control

AI-Based Overtime Verification System for electrical operations. Built with Streamlit and Python, it provides worker, engineer, and supervisor workflows, verifies attendance-based overtime, deducts lunch breaks, analyzes work complexity, flags unusual claims, supports Groq AI summaries, and exports management-ready Excel reports.

## What v2 Includes

- `unified_platform_v2.py` - one polished platform with role selection for Worker, Engineer, Supervisor, and Management Dashboard.
- `worker_portal_v2.py` - individual worker portal.
- `engineer_portal_v2.py` - individual engineer verification and approval portal.
- `supervisor_portal_v2.py` - individual supervisor question, answer review, and approval portal.
- `backend_engine_v2.py` - shared backend, SQLite database, document extraction, risk scoring, Groq hook, and Excel export.
- `practice_overtime_data_v2.xlsx` - sample Excel workbook for testing uploads.

## Download From GitHub

1. Open the GitHub repository.
2. Click the green **Code** button.
3. Choose **Download ZIP**.
4. Extract the ZIP file.
5. Open PowerShell inside the extracted project folder.

Or clone it:

```powershell
git clone <your-repository-url>
cd <your-repository-folder>
```

## Install

Create a virtual environment:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install requirements:

```powershell
python -m pip install -r requirements.txt
```

## Optional Groq Setup

For Groq free-tier AI summaries, set your API key before launching:

```powershell
$env:GROQ_API_KEY="your_groq_api_key"
```

If no Groq key is set, the system still works using the local electrical-industry rules engine.

## Run Recommended Unified Platform

```powershell
streamlit run unified_platform_v2.py --server.port 8501
```

Open:

```text
http://localhost:8501
```

## Run Individual Portals

Worker:

```powershell
streamlit run worker_portal_v2.py --server.port 8501
```

Engineer:

```powershell
streamlit run engineer_portal_v2.py --server.port 8502
```

Supervisor:

```powershell
streamlit run supervisor_portal_v2.py --server.port 8503
```

## Practice Excel File

Use `practice_overtime_data_v2.xlsx` to test uploads. It contains:

- Attendance
- Overtime Claims
- Crew Deployment
- Completion Reports
- Work Benchmarks

## Data Storage

The app stores data in:

```text
data/overtime_phase1.sqlite3
```

Generated reports are saved in:

```text
data/reports
```
