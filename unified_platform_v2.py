from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from backend_engine_v2 import (
    create_claim,
    export_management_excel,
    get_claim,
    list_claims,
    seed_demo_data,
    update_engineer_review,
    update_supervisor_review,
    update_worker_answers,
)


st.set_page_config(page_title="Overtime Control v2", layout="wide")


STATUS_COLORS = {
    "Green": "#15803d",
    "Yellow": "#b45309",
    "Red": "#b91c1c",
}


def apply_style() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background: linear-gradient(180deg, #f8fafc 0%, #eef6f5 42%, #f8fafc 100%);
        }
        .block-container {
            padding-top: 1.4rem;
            max-width: 1280px;
        }
        .hero {
            background: #0f172a;
            color: white;
            padding: 26px 30px;
            border-radius: 8px;
            border-left: 7px solid #14b8a6;
            margin-bottom: 20px;
        }
        .hero h1 {
            margin: 0 0 8px 0;
            font-size: 34px;
            letter-spacing: 0;
        }
        .hero p {
            margin: 0;
            color: #cbd5e1;
            font-size: 16px;
        }
        .role-card {
            background: white;
            border: 1px solid #dbe5e3;
            border-radius: 8px;
            padding: 18px;
            box-shadow: 0 10px 28px rgba(15, 23, 42, 0.06);
        }
        .status-pill {
            display: inline-block;
            color: white;
            padding: 5px 11px;
            border-radius: 999px;
            font-weight: 700;
            font-size: 13px;
        }
        .small-muted {
            color: #64748b;
            font-size: 13px;
        }
        div[data-testid="stMetric"] {
            background: white;
            border: 1px solid #dbe5e3;
            border-radius: 8px;
            padding: 14px;
            box-shadow: 0 8px 20px rgba(15, 23, 42, 0.04);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def header() -> None:
    st.markdown(
        """
        <div class="hero">
            <h1>AI-Based Overtime Verification System v2</h1>
            <p>One platform for worker submission, engineer validation, supervisor questions, risk scoring, approvals, and Excel reporting.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def status_badge(status: str) -> None:
    color = STATUS_COLORS.get(status, "#334155")
    st.markdown(
        f"<span class='status-pill' style='background:{color};'>{status}</span>",
        unsafe_allow_html=True,
    )


def role_selector() -> str:
    return st.sidebar.radio(
        "Choose role",
        ["Worker", "Engineer", "Supervisor", "Management Dashboard"],
        captions=[
            "Submit claims and answer questions",
            "Validate technical work and approve",
            "Ask questions and approve",
            "Reports and analytics",
        ],
    )


def claim_options(df: pd.DataFrame, label: str) -> dict[str, int]:
    if df.empty:
        st.info(f"No claims available for {label}.")
        return {}
    return {
        f"#{row.id} | {row.employee_name} | {row.site or '-'} | {row.analysis_status} | Risk {row.analysis_risk_score}": int(row.id)
        for row in df.itertuples()
    }


def claim_summary(claim: dict) -> None:
    analysis = claim["analysis"]
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Risk", analysis["risk_score"])
    c2.metric("Claimed OT", f"{analysis['claimed_overtime_hours']:.2f} hr")
    c3.metric("Attendance OT", f"{analysis['actual_overtime_hours']:.2f} hr")
    c4.metric("Expected", f"{analysis['expected_hours']:.2f} hr")
    c5.metric("Net work", f"{analysis['net_working_hours']:.2f} hr")

    left, right = st.columns([1.1, 0.9])
    with left:
        st.write(f"**Employee:** {claim['employee_name']} ({claim.get('employee_id') or 'No ID'})")
        st.write(f"**Department:** {claim.get('department') or '-'}")
        st.write(f"**Site:** {claim.get('site') or '-'}")
        st.write(f"**Date/time:** {claim['claim_date']} | {claim['start_time']} to {claim['end_time']}")
        st.write(f"**Work type:** {analysis['work_type'].title()}")
        st.write(f"**Electrical segment:** {analysis['industry_segment']}")
    with right:
        status_badge(analysis["status"])
        st.write(f"**AI recommendation:** {analysis['recommendation']}")
        st.write(f"**Engineer decision:** {claim.get('engineer_decision') or 'Pending'}")
        st.write(f"**Supervisor decision:** {claim.get('supervisor_decision') or 'Pending'}")


def show_flags(analysis: dict) -> None:
    if analysis["flags"]:
        for flag in analysis["flags"]:
            st.warning(flag)
    else:
        st.success("No active flags.")
    if analysis["follow_up_questions"]:
        st.info("AI suggested questions")
        for question in analysis["follow_up_questions"]:
            st.write(f"- {question}")


def render_worker() -> None:
    st.subheader("Worker Portal")
    tab_submit, tab_answer = st.tabs(["Submit overtime", "Answer supervisor"])

    with tab_submit:
        with st.form("worker_claim_v2"):
            left, right = st.columns(2)
            with left:
                employee_name = st.text_input("Employee name")
                employee_id = st.text_input("Employee ID")
                department = st.selectbox(
                    "Department / segment",
                    [
                        "Distribution",
                        "Transmission",
                        "Substation",
                        "Cable",
                        "Metering",
                        "Protection and Control",
                        "Renewable Energy",
                        "Battery Energy Storage",
                        "EV Charging",
                        "Industrial Electrical",
                        "Emergency Response",
                    ],
                )
                site = st.text_input("Site / substation / feeder")
            with right:
                claim_date = st.date_input("Work date", value=date.today())
                start_time = st.time_input("In time")
                end_time = st.time_input("Out time")
                overtime_claimed = st.number_input("Overtime claimed (hours)", min_value=0.0, step=0.25)
            work_description = st.text_area("Work performed", height=115)
            employee_reason = st.text_area("Reason overtime was required", height=95)
            files = st.file_uploader(
                "Upload attendance, completion report, PDF, Excel, CSV, or text",
                accept_multiple_files=True,
                type=["pdf", "xlsx", "xls", "csv", "txt", "log"],
            )
            submitted = st.form_submit_button("Submit claim", type="primary")

        if submitted:
            if not employee_name.strip() or not work_description.strip():
                st.error("Employee name and work performed are required.")
            else:
                claim_id = create_claim(
                    {
                        "employee_name": employee_name.strip(),
                        "employee_id": employee_id.strip(),
                        "department": department,
                        "site": site.strip(),
                        "claim_date": claim_date.isoformat(),
                        "start_time": start_time.strftime("%H:%M"),
                        "end_time": end_time.strftime("%H:%M"),
                        "overtime_claimed": overtime_claimed,
                        "work_description": work_description.strip(),
                        "employee_reason": employee_reason.strip(),
                    },
                    files or [],
                )
                st.success(f"Claim #{claim_id} submitted.")
                claim = get_claim(claim_id)
                if claim:
                    claim_summary(claim)
                    show_flags(claim["analysis"])

    with tab_answer:
        df = list_claims()
        pending = df[df["supervisor_questions"].fillna("").ne("")] if not df.empty else df
        options = claim_options(pending, "worker answers")
        if not options:
            return
        selected = st.selectbox("Select claim", list(options.keys()), key="worker_answer_select")
        claim = get_claim(options[selected])
        if not claim:
            return
        claim_summary(claim)
        st.text_area("Supervisor questions", value=claim.get("supervisor_questions") or "", height=125, disabled=True)
        with st.form(f"worker_answers_v2_{claim['id']}"):
            answers = st.text_area("Your answers", value=claim.get("worker_answers") or "", height=145)
            files = st.file_uploader(
                "Upload additional proof",
                accept_multiple_files=True,
                type=["pdf", "xlsx", "xls", "csv", "txt", "log"],
                key=f"worker_files_v2_{claim['id']}",
            )
            saved = st.form_submit_button("Save worker answers", type="primary")
        if saved:
            update_worker_answers(claim["id"], answers.strip(), files or [])
            st.success("Worker answers saved and risk re-calculated.")
            st.rerun()


def render_engineer() -> None:
    st.subheader("Engineer Portal")
    df = list_claims()
    options = claim_options(df, "engineer verification")
    if not options:
        return
    selected = st.selectbox("Select claim", list(options.keys()), key="engineer_select")
    claim = get_claim(options[selected])
    if not claim:
        return

    claim_summary(claim)
    left, right = st.columns(2)
    with left:
        st.text_area("Worker description", value=claim["work_description"], height=110, disabled=True)
        st.text_area("Worker reason", value=claim.get("employee_reason") or "", height=90, disabled=True)
        st.text_area("Worker answers", value=claim.get("worker_answers") or "", height=90, disabled=True)
    with right:
        st.text_area("Supervisor questions", value=claim.get("supervisor_questions") or "", height=130, disabled=True)
        show_flags(claim["analysis"])

    with st.form(f"engineer_v2_{claim['id']}"):
        engineer_name = st.text_input("Engineer name", value=claim.get("engineer_name") or "")
        root_cause = st.text_area("Technical root cause", value=claim.get("engineer_root_cause") or "", height=95)
        extra_work = st.text_area("Additional work discovered", value=claim.get("engineer_extra_work") or "", height=105)
        safety_notes = st.text_area(
            "Safety, permit, testing, and restoration notes",
            value=claim.get("engineer_safety_notes") or "",
            height=105,
        )
        engineer_answers = st.text_area(
            "Answers to supervisor questions",
            value=claim.get("engineer_answers") or "",
            height=120,
        )
        c1, c2 = st.columns(2)
        with c1:
            recommendation = st.selectbox(
                "Engineer recommendation",
                ["Technically Justified", "Needs More Evidence", "Not Technically Justified", "Escalate to Management"],
                index=[
                    "Technically Justified",
                    "Needs More Evidence",
                    "Not Technically Justified",
                    "Escalate to Management",
                ].index(claim.get("engineer_recommendation") or "Needs More Evidence")
                if (claim.get("engineer_recommendation") or "Needs More Evidence")
                in [
                    "Technically Justified",
                    "Needs More Evidence",
                    "Not Technically Justified",
                    "Escalate to Management",
                ]
                else 1,
            )
        with c2:
            decision = st.selectbox(
                "Engineer approval",
                ["Pending", "Approve", "Reject", "Escalate"],
                index=["Pending", "Approve", "Reject", "Escalate"].index(
                    claim.get("engineer_decision") or "Pending"
                )
                if (claim.get("engineer_decision") or "Pending") in ["Pending", "Approve", "Reject", "Escalate"]
                else 0,
            )
        files = st.file_uploader(
            "Upload engineering documents",
            accept_multiple_files=True,
            type=["pdf", "xlsx", "xls", "csv", "txt", "log"],
            key=f"engineer_files_v2_{claim['id']}",
        )
        saved = st.form_submit_button("Save engineer verification", type="primary")
    if saved:
        if not engineer_name.strip():
            st.error("Engineer name is required.")
        else:
            update_engineer_review(
                claim_id=claim["id"],
                engineer_name=engineer_name.strip(),
                root_cause=root_cause.strip(),
                extra_work=extra_work.strip(),
                safety_notes=safety_notes.strip(),
                engineer_answers=engineer_answers.strip(),
                recommendation=recommendation,
                decision=decision,
                files=files or [],
            )
            st.success("Engineer verification saved and risk re-calculated.")
            st.rerun()


def render_supervisor() -> None:
    st.subheader("Supervisor Portal")
    df = list_claims()
    options = claim_options(df, "supervisor review")
    if not options:
        return
    selected = st.selectbox("Select claim", list(options.keys()), key="supervisor_select")
    claim = get_claim(options[selected])
    if not claim:
        return

    claim_summary(claim)
    tabs = st.tabs(["Questions and answers", "Evidence", "Approval"])
    with tabs[0]:
        left, right = st.columns(2)
        with left:
            st.text_area("Worker answer", value=claim.get("worker_answers") or "", height=130, disabled=True)
            st.text_area("Engineer answer", value=claim.get("engineer_answers") or "", height=130, disabled=True)
        with right:
            show_flags(claim["analysis"])
            st.text_area("AI summary", value=claim["analysis"]["ai_summary"], height=140, disabled=True)
        with st.form(f"supervisor_questions_v2_{claim['id']}"):
            supervisor_name = st.text_input("Supervisor name", value=claim.get("supervisor_name") or "")
            questions = st.text_area(
                "Questions to worker and engineer",
                value=claim.get("supervisor_questions") or "",
                placeholder=(
                    "Ask what caused the overtime, what additional work was discovered, "
                    "how much time it consumed, and what proof/testing confirms it."
                ),
                height=145,
            )
            decision = st.selectbox(
                "Supervisor approval",
                ["Pending Review", "Approve", "Reject", "Escalate"],
                index=["Pending Review", "Approve", "Reject", "Escalate"].index(
                    claim.get("supervisor_decision") or "Pending Review"
                )
                if (claim.get("supervisor_decision") or "Pending Review")
                in ["Pending Review", "Approve", "Reject", "Escalate"]
                else 0,
            )
            files = st.file_uploader(
                "Upload supervisor documents",
                accept_multiple_files=True,
                type=["pdf", "xlsx", "xls", "csv", "txt", "log"],
                key=f"supervisor_files_v2_{claim['id']}",
            )
            saved = st.form_submit_button("Save supervisor review", type="primary")
        if saved:
            if not supervisor_name.strip():
                st.error("Supervisor name is required.")
            else:
                update_supervisor_review(
                    claim_id=claim["id"],
                    supervisor_name=supervisor_name.strip(),
                    supervisor_questions=questions.strip(),
                    decision=decision,
                    files=files or [],
                )
                st.success("Supervisor review saved and risk re-calculated.")
                st.rerun()

    with tabs[1]:
        st.json(
            {
                "worker_files": claim.get("uploaded_files") or [],
                "engineer_files": claim.get("engineer_documents") or [],
                "supervisor_files": claim.get("supervisor_documents") or [],
            }
        )
        st.text_area("Extracted evidence text", value=claim.get("extracted_text") or "", height=260, disabled=True)

    with tabs[2]:
        final_ready = (
            claim.get("engineer_decision") == "Approve"
            and claim.get("supervisor_decision") == "Approve"
            and claim["analysis"]["status"] == "Green"
        )
        if final_ready:
            st.success("Final status: Approved by engineer and supervisor with Green risk.")
        elif claim.get("supervisor_decision") == "Approve" or claim.get("engineer_decision") == "Approve":
            st.warning("Partial approval exists. Final closure needs both engineer and supervisor decisions aligned.")
        else:
            st.info("Awaiting approvals.")


def render_dashboard() -> None:
    st.subheader("Management Dashboard")
    df = list_claims()
    if df.empty:
        st.info("No claims submitted.")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Claims", len(df))
    c2.metric("Total OT claimed", f"{df['overtime_claimed'].sum():.2f} hr")
    c3.metric("Engineer approved", int((df["engineer_decision"] == "Approve").sum()))
    c4.metric("Supervisor approved", int((df["supervisor_decision"] == "Approve").sum()))

    cols = [
        "id",
        "employee_name",
        "department",
        "site",
        "claim_date",
        "overtime_claimed",
        "analysis_risk_score",
        "analysis_status",
        "engineer_decision",
        "supervisor_decision",
    ]
    st.dataframe(df[[col for col in cols if col in df.columns]], use_container_width=True, hide_index=True)

    left, right = st.columns(2)
    with left:
        st.write("Risk status")
        st.bar_chart(df.groupby("analysis_status").size().reset_index(name="count"), x="analysis_status", y="count")
    with right:
        st.write("Department overtime")
        st.bar_chart(
            df.groupby("department", dropna=False)["overtime_claimed"].sum().reset_index(),
            x="department",
            y="overtime_claimed",
        )

    if st.button("Generate Excel report", type="primary"):
        path = export_management_excel()
        st.success(f"Report generated: {path}")
        with open(path, "rb") as handle:
            st.download_button(
                "Download Excel report",
                data=handle,
                file_name=path.name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )


def main() -> None:
    apply_style()
    seed_demo_data()
    header()
    role = role_selector()
    if role == "Worker":
        render_worker()
    elif role == "Engineer":
        render_engineer()
    elif role == "Supervisor":
        render_supervisor()
    else:
        render_dashboard()


if __name__ == "__main__":
    main()
