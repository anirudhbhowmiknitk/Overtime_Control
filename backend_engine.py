from __future__ import annotations

import json
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover - optional at runtime
    PdfReader = None


APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "overtime_phase1.sqlite3"
REPORT_DIR = DATA_DIR / "reports"


SHIFT_HOURS = 8.0
STANDARD_LUNCH_HOURS = 1.0


ELECTRICAL_WORK_CATALOG: dict[str, dict[str, Any]] = {
    "fuse replacement": {
        "hours": 0.75,
        "keywords": ["fuse", "kitkat", "dropout", "cutout"],
        "industry": "distribution",
    },
    "meter replacement": {
        "hours": 0.5,
        "keywords": ["meter", "ami", "smart meter", "ct meter", "energy meter"],
        "industry": "metering",
    },
    "transformer maintenance": {
        "hours": 2.5,
        "keywords": ["transformer", "trf", "dt", "oil", "bushing", "oltc", "lug"],
        "industry": "distribution/substation",
    },
    "cable fault repair": {
        "hours": 4.0,
        "keywords": ["cable", "joint", "termination", "megger", "fault", "lugs"],
        "industry": "underground distribution",
    },
    "overhead line repair": {
        "hours": 3.0,
        "keywords": ["overhead", "conductor", "pole", "insulator", "jumper", "stay"],
        "industry": "overhead distribution/transmission",
    },
    "feeder restoration": {
        "hours": 2.0,
        "keywords": ["feeder", "trip", "restoration", "outage", "load transfer"],
        "industry": "distribution control",
    },
    "substation switching": {
        "hours": 1.5,
        "keywords": ["substation", "switching", "isolator", "breaker", "bus", "permit"],
        "industry": "substation operations",
    },
    "relay protection testing": {
        "hours": 4.0,
        "keywords": ["relay", "protection", "secondary injection", "trip test", "scheme"],
        "industry": "protection and control",
    },
    "switchgear maintenance": {
        "hours": 3.5,
        "keywords": ["switchgear", "vcb", "acb", "rmu", "breaker", "panel"],
        "industry": "substation/industrial",
    },
    "earthing and safety work": {
        "hours": 2.0,
        "keywords": ["earthing", "earth pit", "safety", "ppe", "loto"],
        "industry": "electrical safety",
    },
    "solar inverter maintenance": {
        "hours": 2.0,
        "keywords": ["solar", "inverter", "pv", "string", "mppt"],
        "industry": "renewable energy",
    },
    "battery energy storage work": {
        "hours": 3.0,
        "keywords": ["battery", "bess", "pcs", "bms", "energy storage"],
        "industry": "energy storage",
    },
    "ev charger repair": {
        "hours": 1.5,
        "keywords": ["ev", "charger", "charging", "connector", "ocpp"],
        "industry": "electric mobility",
    },
    "industrial electrical maintenance": {
        "hours": 3.0,
        "keywords": ["motor", "mcc", "starter", "vfd", "drive", "plant"],
        "industry": "industrial electrical",
    },
    "emergency breakdown": {
        "hours": 3.0,
        "keywords": ["emergency", "breakdown", "fire", "storm", "flood", "critical"],
        "industry": "emergency response",
    },
}


@dataclass
class ClaimAnalysis:
    work_type: str
    industry_segment: str
    expected_hours: float
    presence_hours: float
    net_working_hours: float
    actual_overtime_hours: float
    claimed_overtime_hours: float
    risk_score: int
    status: str
    recommendation: str
    flags: list[str]
    follow_up_questions: list[str]
    ai_summary: str


def init_db() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    UPLOAD_DIR.mkdir(exist_ok=True)
    REPORT_DIR.mkdir(exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS claims (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_name TEXT NOT NULL,
                employee_id TEXT,
                department TEXT,
                site TEXT,
                claim_date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                overtime_claimed REAL NOT NULL,
                work_description TEXT NOT NULL,
                employee_reason TEXT,
                uploaded_files TEXT NOT NULL DEFAULT '[]',
                extracted_text TEXT,
                supervisor_name TEXT,
                supervisor_remarks TEXT,
                supervisor_documents TEXT NOT NULL DEFAULT '[]',
                supervisor_decision TEXT,
                analysis_json TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _parse_clock(value: str, claim_date: str) -> datetime:
    clean = value.strip().upper()
    for fmt in ("%H:%M", "%I:%M %p", "%I:%M%p"):
        try:
            time_value = datetime.strptime(clean, fmt).time()
            return datetime.fromisoformat(claim_date).replace(
                hour=time_value.hour, minute=time_value.minute, second=0, microsecond=0
            )
        except ValueError:
            continue
    raise ValueError(f"Invalid time: {value}")


def calculate_hours(claim_date: str, start_time: str, end_time: str) -> tuple[float, float, float]:
    start = _parse_clock(start_time, claim_date)
    end = _parse_clock(end_time, claim_date)
    if end <= start:
        end += timedelta(days=1)
    presence = round((end - start).total_seconds() / 3600, 2)
    lunch = STANDARD_LUNCH_HOURS if presence >= 6 else 0.0
    net = max(0.0, round(presence - lunch, 2))
    actual_ot = max(0.0, round(net - SHIFT_HOURS, 2))
    return presence, net, actual_ot


def classify_work_type(text: str) -> tuple[str, str, float]:
    haystack = text.lower()
    best_name = "general electrical maintenance"
    best_score = 0
    best = {"hours": 2.5, "industry": "general electrical"}
    for name, meta in ELECTRICAL_WORK_CATALOG.items():
        score = sum(1 for keyword in meta["keywords"] if keyword in haystack)
        if score > best_score:
            best_name = name
            best_score = score
            best = meta
    return best_name, str(best["industry"]), float(best["hours"])


def _repeated_reason_penalty(reason: str) -> int:
    if not DB_PATH.exists() or not reason.strip():
        return 0
    normalized = re.sub(r"\s+", " ", reason.lower()).strip()
    if len(normalized) < 12:
        return 0
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT employee_reason FROM claims").fetchall()
    matches = 0
    for (old_reason,) in rows:
        old = re.sub(r"\s+", " ", (old_reason or "").lower()).strip()
        if old == normalized:
            matches += 1
    return 10 if matches >= 2 else 0


def _groq_summary(payload: dict[str, Any]) -> str:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return "Groq not configured. Used local electrical-industry rule engine."
    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        prompt = (
            "You are verifying overtime for electrical industry operations. "
            "Give a concise technical assessment, mention whether the overtime is justified, "
            "and name any missing evidence. Return plain text only.\n\n"
            f"{json.dumps(payload, ensure_ascii=True, indent=2)}"
        )
        completion = client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=220,
        )
        return completion.choices[0].message.content.strip()
    except Exception as exc:
        return f"Groq call failed, so local rule engine was used. Error: {exc}"


def analyze_claim(payload: dict[str, Any], extracted_text: str = "") -> ClaimAnalysis:
    combined_text = " ".join(
        [
            payload.get("work_description", ""),
            payload.get("employee_reason", ""),
            payload.get("supervisor_remarks", ""),
            extracted_text or "",
        ]
    )
    work_type, industry_segment, expected_hours = classify_work_type(combined_text)
    presence, net, actual_ot = calculate_hours(
        payload["claim_date"], payload["start_time"], payload["end_time"]
    )
    claimed_ot = float(payload.get("overtime_claimed") or 0)

    flags: list[str] = []
    questions: list[str] = []
    risk = 5

    if claimed_ot > actual_ot + 0.25:
        risk += 25
        flags.append("Attendance mismatch: claimed overtime exceeds lunch-adjusted overtime.")
        questions.append("Explain why claimed overtime is higher than attendance-based overtime.")
    if net > expected_hours * 1.75 and net - expected_hours > 1.0:
        risk += 20
        flags.append("Excessive duration compared with historical electrical work benchmark.")
        questions.append("What additional technical work increased the job duration?")
    if claimed_ot >= 4:
        risk += 15
        flags.append("High overtime claim.")
    if not payload.get("employee_reason", "").strip():
        risk += 15
        flags.append("Missing employee overtime justification.")
        questions.append("Why could this task not be completed in normal working hours?")
    if not extracted_text.strip():
        risk += 10
        flags.append("No readable supporting document text found.")
        questions.append("Upload completion, attendance, or maintenance evidence.")
    if any(word in combined_text.lower() for word in ["emergency", "trip", "outage", "breakdown", "storm"]):
        risk = max(0, risk - 12)
    risk += _repeated_reason_penalty(payload.get("employee_reason", ""))

    if payload.get("supervisor_remarks"):
        remarks = payload["supervisor_remarks"].lower()
        technical_terms = ["fault", "cable", "transformer", "relay", "feeder", "breaker", "meter", "safety"]
        if any(term in remarks for term in technical_terms):
            risk = max(0, risk - 12)
        else:
            risk += 8
            flags.append("Supervisor response is not technically specific.")
            questions.append("Supervisor should identify the extra activity and time consumed.")

    risk = max(0, min(100, int(risk)))
    if risk <= 30:
        status = "Green"
        recommendation = "Approve"
    elif risk <= 65:
        status = "Yellow"
        recommendation = "Review"
    else:
        status = "Red"
        recommendation = "Escalate"

    groq_payload = {
        "work_type": work_type,
        "industry_segment": industry_segment,
        "expected_hours": expected_hours,
        "presence_hours": presence,
        "net_working_hours_after_lunch": net,
        "attendance_based_overtime": actual_ot,
        "claimed_overtime": claimed_ot,
        "flags": flags,
        "supervisor_remarks": payload.get("supervisor_remarks", ""),
    }
    ai_summary = _groq_summary(groq_payload)

    return ClaimAnalysis(
        work_type=work_type,
        industry_segment=industry_segment,
        expected_hours=expected_hours,
        presence_hours=presence,
        net_working_hours=net,
        actual_overtime_hours=actual_ot,
        claimed_overtime_hours=claimed_ot,
        risk_score=risk,
        status=status,
        recommendation=recommendation,
        flags=flags,
        follow_up_questions=list(dict.fromkeys(questions)),
        ai_summary=ai_summary,
    )


def save_uploaded_files(files: list[Any], prefix: str) -> tuple[list[dict[str, str]], str]:
    saved: list[dict[str, str]] = []
    extracted_parts: list[str] = []
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    for file in files:
        if file is None:
            continue
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", file.name)
        target = UPLOAD_DIR / f"{prefix}_{safe_name}"
        target.write_bytes(file.getbuffer())
        saved.append({"name": file.name, "path": str(target)})
        extracted_parts.append(extract_document_text(target))
    return saved, "\n".join(part for part in extracted_parts if part)


def extract_document_text(path: Path) -> str:
    suffix = path.suffix.lower()
    try:
        if suffix == ".pdf" and PdfReader:
            reader = PdfReader(str(path))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        if suffix in {".xlsx", ".xls"}:
            sheets = pd.read_excel(path, sheet_name=None)
            return "\n".join(df.to_csv(index=False) for df in sheets.values())
        if suffix == ".csv":
            return pd.read_csv(path).to_csv(index=False)
        if suffix in {".txt", ".log"}:
            return path.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:
        return f"Could not extract {path.name}: {exc}"
    return ""


def create_claim(payload: dict[str, Any], files: list[Any]) -> int:
    init_db()
    timestamp = _now()
    saved_files, extracted_text = save_uploaded_files(files, f"claim_{timestamp.replace(':', '-')}")
    analysis = analyze_claim(payload, extracted_text)
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            """
            INSERT INTO claims (
                employee_name, employee_id, department, site, claim_date, start_time, end_time,
                overtime_claimed, work_description, employee_reason, uploaded_files, extracted_text,
                analysis_json, status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["employee_name"],
                payload.get("employee_id", ""),
                payload.get("department", ""),
                payload.get("site", ""),
                payload["claim_date"],
                payload["start_time"],
                payload["end_time"],
                float(payload.get("overtime_claimed") or 0),
                payload["work_description"],
                payload.get("employee_reason", ""),
                json.dumps(saved_files),
                extracted_text,
                json.dumps(analysis.__dict__),
                analysis.status,
                timestamp,
                timestamp,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def list_claims() -> pd.DataFrame:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query("SELECT * FROM claims ORDER BY created_at DESC", conn)
    if df.empty:
        return df
    analysis = df["analysis_json"].apply(json.loads).apply(pd.Series)
    return pd.concat([df.drop(columns=["analysis_json"]), analysis.add_prefix("analysis_")], axis=1)


def get_claim(claim_id: int) -> dict[str, Any] | None:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
    if row is None:
        return None
    item = dict(row)
    item["analysis"] = json.loads(item.pop("analysis_json"))
    item["uploaded_files"] = json.loads(item.get("uploaded_files") or "[]")
    item["supervisor_documents"] = json.loads(item.get("supervisor_documents") or "[]")
    return item


def update_supervisor_review(
    claim_id: int,
    supervisor_name: str,
    supervisor_remarks: str,
    decision: str,
    files: list[Any],
) -> None:
    claim = get_claim(claim_id)
    if not claim:
        raise ValueError("Claim not found")
    saved_files, extracted_text = save_uploaded_files(files, f"supervisor_{claim_id}_{_now().replace(':', '-')}")
    combined_extracted = "\n".join([claim.get("extracted_text") or "", extracted_text]).strip()
    payload = {
        **claim,
        "supervisor_remarks": supervisor_remarks,
        "claim_date": claim["claim_date"],
        "start_time": claim["start_time"],
        "end_time": claim["end_time"],
        "overtime_claimed": claim["overtime_claimed"],
        "work_description": claim["work_description"],
        "employee_reason": claim.get("employee_reason") or "",
    }
    analysis = analyze_claim(payload, combined_extracted)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            UPDATE claims
            SET supervisor_name = ?, supervisor_remarks = ?, supervisor_documents = ?,
                supervisor_decision = ?, extracted_text = ?, analysis_json = ?,
                status = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                supervisor_name,
                supervisor_remarks,
                json.dumps((claim.get("supervisor_documents") or []) + saved_files),
                decision,
                combined_extracted,
                json.dumps(analysis.__dict__),
                analysis.status,
                _now(),
                claim_id,
            ),
        )
        conn.commit()


def export_management_excel() -> Path:
    df = list_claims()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    target = REPORT_DIR / f"overtime_management_report_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
    if df.empty:
        df = pd.DataFrame(columns=["No claims submitted"])
    report_cols = [
        "id",
        "employee_name",
        "department",
        "site",
        "claim_date",
        "start_time",
        "end_time",
        "overtime_claimed",
        "analysis_expected_hours",
        "analysis_net_working_hours",
        "analysis_actual_overtime_hours",
        "analysis_risk_score",
        "analysis_status",
        "analysis_recommendation",
        "analysis_flags",
        "supervisor_name",
        "supervisor_decision",
    ]
    available = [col for col in report_cols if col in df.columns]
    with pd.ExcelWriter(target, engine="openpyxl") as writer:
        df[available].to_excel(writer, index=False, sheet_name="Claim Dashboard")
        if not df.empty and "analysis_status" in df:
            summary = df.groupby("analysis_status").size().reset_index(name="count")
            summary.to_excel(writer, index=False, sheet_name="Risk Summary")
        if not df.empty and "department" in df:
            dept = (
                df.groupby("department", dropna=False)["overtime_claimed"]
                .sum()
                .reset_index(name="total_claimed_ot")
            )
            dept.to_excel(writer, index=False, sheet_name="Department OT")
    return target


def seed_demo_data() -> None:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        count = conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
    if count:
        return
    samples = [
        {
            "employee_name": "Raj",
            "employee_id": "E101",
            "department": "Distribution",
            "site": "Powai DSS",
            "claim_date": "2026-06-01",
            "start_time": "09:00",
            "end_time": "20:00",
            "overtime_claimed": 2,
            "work_description": "Transformer maintenance completed with oil leakage inspection.",
            "employee_reason": "Work extended due to bushing cleaning and final safety checks.",
        },
        {
            "employee_name": "Sunil",
            "employee_id": "E118",
            "department": "Cable",
            "site": "Market City",
            "claim_date": "2026-06-05",
            "start_time": "09:00",
            "end_time": "23:00",
            "overtime_claimed": 6,
            "work_description": "Cable fault repair and termination work.",
            "employee_reason": "",
        },
    ]
    for sample in samples:
        create_claim(sample, [])
