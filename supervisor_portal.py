from __future__ import annotations

import json

import streamlit as st

from backend_engine import (
    export_management_excel,
    get_claim,
    list_claims,
    seed_demo_data,
    update_supervisor_review,
)


st.set_page_config(page_title="Supervisor Overtime Portal", layout="wide")


STATUS_COLORS = {
    "Green": "#15803d",
    "Yellow": "#a16207",
    "Red": "#b91c1c",
}


def main() -> None:
    seed_demo_data()
    st.title("Supervisor Overtime Portal")
    st.caption("Review flagged claims, add technical verification, and export management reports.")

    df = list_claims()
    if df.empty:
        st.info("No claims have been submitted yet.")
        return

    top = st.columns(4)
    top[0].metric("Total claims", len(df))
    top[1].metric("Green", int((df["analysis_status"] == "Green").sum()))
    top[2].metric("Yellow", int((df["analysis_status"] == "Yellow").sum()))
    top[3].metric("Red", int((df["analysis_status"] == "Red").sum()))

    tab_review, tab_dashboard, tab_export = st.tabs(["Review", "Dashboard", "Excel report"])

    with tab_review:
        review_claim(df)
    with tab_dashboard:
        show_dashboard(df)
    with tab_export:
        show_export()


def review_claim(df) -> None:
    options = {
        f"#{row.id} | {row.employee_name} | {row.claim_date} | {row.analysis_status} | Risk {row.analysis_risk_score}": int(row.id)
        for row in df.itertuples()
    }
    selected = st.selectbox("Select claim", list(options.keys()))
    claim_id = options[selected]
    claim = get_claim(claim_id)
    if not claim:
        st.error("Claim not found.")
        return

    analysis = claim["analysis"]
    color = STATUS_COLORS.get(analysis["status"], "#334155")
    st.markdown(
        f"<h3 style='color:{color};'>Claim #{claim_id}: {analysis['status']} / {analysis['recommendation']}</h3>",
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Risk", analysis["risk_score"])
    c2.metric("Claimed OT", f"{analysis['claimed_overtime_hours']:.2f} hr")
    c3.metric("Attendance OT", f"{analysis['actual_overtime_hours']:.2f} hr")
    c4.metric("Net hours", f"{analysis['net_working_hours']:.2f} hr")
    c5.metric("Expected", f"{analysis['expected_hours']:.2f} hr")

    left, right = st.columns([1, 1])
    with left:
        st.subheader("Employee submission")
        st.write(f"**Employee:** {claim['employee_name']} ({claim.get('employee_id') or 'No ID'})")
        st.write(f"**Department:** {claim.get('department') or '-'}")
        st.write(f"**Site:** {claim.get('site') or '-'}")
        st.write(f"**Time:** {claim['start_time']} to {claim['end_time']}")
        st.write(f"**Work type:** {analysis['work_type'].title()}")
        st.write(f"**Industry segment:** {analysis['industry_segment']}")
        st.text_area("Work performed", value=claim["work_description"], height=120, disabled=True)
        st.text_area("Employee reason", value=claim.get("employee_reason") or "", height=100, disabled=True)

    with right:
        st.subheader("AI verification")
        if analysis["flags"]:
            for flag in analysis["flags"]:
                st.warning(flag)
        else:
            st.success("No current flags.")
        if analysis["follow_up_questions"]:
            st.info("Follow-up questions")
            for question in analysis["follow_up_questions"]:
                st.write(f"- {question}")
        st.text_area("AI summary", value=analysis["ai_summary"], height=150, disabled=True)

    with st.expander("Uploaded evidence and extracted text"):
        st.write("Employee files")
        st.json(claim.get("uploaded_files") or [])
        st.write("Supervisor files")
        st.json(claim.get("supervisor_documents") or [])
        st.text_area("Extracted document text", value=claim.get("extracted_text") or "", height=220, disabled=True)

    st.subheader("Supervisor verification")
    with st.form(f"supervisor_form_{claim_id}"):
        supervisor_name = st.text_input("Supervisor name", value=claim.get("supervisor_name") or "")
        supervisor_remarks = st.text_area(
            "Technical remarks",
            value=claim.get("supervisor_remarks") or "",
            placeholder="Example: Additional cable damage found during transformer maintenance; terminal lugs replaced and insulation tested.",
            height=130,
        )
        decision = st.selectbox(
            "Supervisor decision",
            ["Pending Review", "Approve", "Reject", "Escalate"],
            index=["Pending Review", "Approve", "Reject", "Escalate"].index(
                claim.get("supervisor_decision") or "Pending Review"
            )
            if (claim.get("supervisor_decision") or "Pending Review")
            in ["Pending Review", "Approve", "Reject", "Escalate"]
            else 0,
        )
        files = st.file_uploader(
            "Upload supervisor report, permit, completion proof, or shift record",
            accept_multiple_files=True,
            type=["pdf", "xlsx", "xls", "csv", "txt", "log"],
        )
        submitted = st.form_submit_button("Save review and re-run AI verification", type="primary")
    if submitted:
        if not supervisor_name.strip():
            st.error("Supervisor name is required.")
            return
        update_supervisor_review(
            claim_id=claim_id,
            supervisor_name=supervisor_name.strip(),
            supervisor_remarks=supervisor_remarks.strip(),
            decision=decision,
            files=files or [],
        )
        st.success("Supervisor review saved and claim re-analyzed.")
        st.rerun()


def show_dashboard(df) -> None:
    st.subheader("Management dashboard")
    display = df[
        [
            "id",
            "employee_name",
            "department",
            "site",
            "claim_date",
            "overtime_claimed",
            "analysis_actual_overtime_hours",
            "analysis_expected_hours",
            "analysis_risk_score",
            "analysis_status",
            "analysis_recommendation",
            "supervisor_decision",
        ]
    ].copy()
    st.dataframe(display, use_container_width=True, hide_index=True)

    left, right = st.columns(2)
    with left:
        st.write("Department-wise overtime")
        dept = df.groupby("department", dropna=False)["overtime_claimed"].sum().reset_index()
        st.bar_chart(dept, x="department", y="overtime_claimed")
    with right:
        st.write("Risk status split")
        status = df.groupby("analysis_status").size().reset_index(name="count")
        st.bar_chart(status, x="analysis_status", y="count")

    st.write("Common flags")
    all_flags: list[str] = []
    for raw in df["analysis_flags"]:
        if isinstance(raw, list):
            all_flags.extend(raw)
        else:
            try:
                all_flags.extend(json.loads(raw.replace("'", '"')))
            except Exception:
                pass
    if all_flags:
        flag_df = (
            __import__("pandas")
            .DataFrame({"flag": all_flags})
            .groupby("flag")
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
        )
        st.dataframe(flag_df, use_container_width=True, hide_index=True)
    else:
        st.success("No flags found.")


def show_export() -> None:
    st.subheader("Excel-based output dashboard")
    st.write(
        "Generates the Phase 1 management workbook with claim dashboard, risk summary, "
        "and department-wise overtime sheets."
    )
    if st.button("Generate Excel report", type="primary"):
        path = export_management_excel()
        st.success(f"Report generated: {path}")
        with open(path, "rb") as handle:
            st.download_button(
                "Download report",
                data=handle,
                file_name=path.name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )


if __name__ == "__main__":
    main()
