from __future__ import annotations

import streamlit as st

from backend_engine import get_claim, list_claims, seed_demo_data, update_engineer_review


STATUS_COLORS = {
    "Green": "#15803d",
    "Yellow": "#a16207",
    "Red": "#b91c1c",
}


def render_engineer_portal() -> None:
    seed_demo_data()
    st.title("Engineer Verification Portal")
    st.caption("Technical validation for electrical overtime claims before final supervisor approval.")

    df = list_claims()
    if df.empty:
        st.info("No claims have been submitted yet.")
        return

    pending = df[df["engineer_name"].fillna("").eq("")]
    c1, c2, c3 = st.columns(3)
    c1.metric("Total claims", len(df))
    c2.metric("Awaiting engineer", len(pending))
    c3.metric("High risk", int((df["analysis_status"] == "Red").sum()))

    options = {
        f"#{row.id} | {row.employee_name} | {row.site or '-'} | {row.analysis_status} | {row.analysis_work_type}": int(row.id)
        for row in df.itertuples()
    }
    selected = st.selectbox("Select claim for technical verification", list(options.keys()))
    claim_id = options[selected]
    claim = get_claim(claim_id)
    if not claim:
        st.error("Claim not found.")
        return

    analysis = claim["analysis"]
    color = STATUS_COLORS.get(analysis["status"], "#334155")
    st.markdown(
        f"<h3 style='color:{color};'>Claim #{claim_id}: {analysis['status']} / Risk {analysis['risk_score']}</h3>",
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Work type", analysis["work_type"].title())
    c2.metric("Expected", f"{analysis['expected_hours']:.2f} hr")
    c3.metric("Net work", f"{analysis['net_working_hours']:.2f} hr")
    c4.metric("Claimed OT", f"{analysis['claimed_overtime_hours']:.2f} hr")

    left, right = st.columns(2)
    with left:
        st.subheader("Claim details")
        st.write(f"**Employee:** {claim['employee_name']} ({claim.get('employee_id') or 'No ID'})")
        st.write(f"**Department:** {claim.get('department') or '-'}")
        st.write(f"**Site:** {claim.get('site') or '-'}")
        st.write(f"**Work date:** {claim['claim_date']}")
        st.write(f"**Attendance:** {claim['start_time']} to {claim['end_time']}")
        st.text_area("Worker description", value=claim["work_description"], height=120, disabled=True)
        st.text_area("Worker reason", value=claim.get("employee_reason") or "", height=90, disabled=True)
    with right:
        st.subheader("AI questions")
        if analysis["flags"]:
            for flag in analysis["flags"]:
                st.warning(flag)
        else:
            st.success("No active technical flags.")
        if analysis["follow_up_questions"]:
            for question in analysis["follow_up_questions"]:
                st.write(f"- {question}")
        st.text_area("AI summary", value=analysis["ai_summary"], height=130, disabled=True)

    with st.expander("Existing supervisor/engineer notes"):
        st.text_area("Supervisor questions", value=claim.get("supervisor_questions") or "", height=110, disabled=True)
        st.text_area("Worker answers", value=claim.get("worker_answers") or "", height=100, disabled=True)
        st.text_area("Supervisor remarks", value=claim.get("supervisor_remarks") or "", height=90, disabled=True)
        st.text_area("Engineer root cause", value=claim.get("engineer_root_cause") or "", height=90, disabled=True)
        st.text_area("Engineer extra work", value=claim.get("engineer_extra_work") or "", height=90, disabled=True)
        st.text_area("Engineer safety notes", value=claim.get("engineer_safety_notes") or "", height=90, disabled=True)

    st.subheader("Engineering verification")
    with st.form(f"engineer_form_{claim_id}"):
        engineer_name = st.text_input("Engineer name", value=claim.get("engineer_name") or "")
        root_cause = st.text_area(
            "Technical root cause",
            value=claim.get("engineer_root_cause") or "",
            placeholder="Example: LT cable termination overheated due to loose lug and insulation damage.",
            height=100,
        )
        extra_work = st.text_area(
            "Additional work discovered",
            value=claim.get("engineer_extra_work") or "",
            placeholder="Example: Replaced damaged lugs, megger tested cable, tightened panel terminations, restored feeder load.",
            height=110,
        )
        safety_notes = st.text_area(
            "Safety, permit, testing, and restoration notes",
            value=claim.get("engineer_safety_notes") or "",
            placeholder="Mention isolation, PTW/LOTO, earthing, PPE, testing, charging clearance, or SCADA/event confirmation.",
            height=110,
        )
        engineer_answers = st.text_area(
            "Answers to supervisor questions",
            value=claim.get("engineer_answers") or "",
            placeholder="Answer the supervisor's technical questions with exact observations, test results, and time impact.",
            height=120,
        )
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
        decision = st.selectbox(
            "Engineer approval decision",
            ["Pending", "Approve", "Reject", "Escalate"],
            index=["Pending", "Approve", "Reject", "Escalate"].index(
                claim.get("engineer_decision") or "Pending"
            )
            if (claim.get("engineer_decision") or "Pending") in ["Pending", "Approve", "Reject", "Escalate"]
            else 0,
        )
        files = st.file_uploader(
            "Upload engineering proof, test report, permit, fault report, photos log, PDF, Excel, CSV, or text",
            accept_multiple_files=True,
            type=["pdf", "xlsx", "xls", "csv", "txt", "log"],
        )
        submitted = st.form_submit_button("Save engineering verification", type="primary")

    if submitted:
        if not engineer_name.strip():
            st.error("Engineer name is required.")
            return
        update_engineer_review(
            claim_id=claim_id,
            engineer_name=engineer_name.strip(),
            root_cause=root_cause.strip(),
            extra_work=extra_work.strip(),
            safety_notes=safety_notes.strip(),
            engineer_answers=engineer_answers.strip(),
            recommendation=recommendation,
            decision=decision,
            files=files or [],
        )
        st.success("Engineering verification saved and claim re-analyzed.")
        st.rerun()


if __name__ == "__main__":
    st.set_page_config(page_title="Engineer Verification Portal", layout="wide")
    render_engineer_portal()
