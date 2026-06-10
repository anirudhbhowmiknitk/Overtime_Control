from __future__ import annotations

from datetime import date

import streamlit as st

from backend_engine import create_claim, get_claim, seed_demo_data


st.set_page_config(page_title="Worker Overtime Portal", layout="wide")


def main() -> None:
    seed_demo_data()
    st.title("Worker Overtime Portal")
    st.caption("Phase 1 standalone submission portal for electrical industry overtime verification.")

    with st.form("worker_claim", clear_on_submit=False):
        left, right = st.columns(2)
        with left:
            employee_name = st.text_input("Employee name", placeholder="Enter full name")
            employee_id = st.text_input("Employee ID", placeholder="E101")
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
            site = st.text_input("Site / substation / feeder", placeholder="Powai DSS / Feeder 4")
        with right:
            claim_date = st.date_input("Work date", value=date.today())
            start_time = st.time_input("In time")
            end_time = st.time_input("Out time")
            overtime_claimed = st.number_input("Overtime claimed (hours)", min_value=0.0, step=0.25)

        work_description = st.text_area(
            "Work performed",
            placeholder="Example: Transformer maintenance completed. Damaged cable lugs discovered and replaced.",
            height=120,
        )
        employee_reason = st.text_area(
            "Reason overtime was required",
            placeholder="Mention emergency, additional fault, safety isolation, access delay, permit delay, material delay, etc.",
            height=100,
        )
        files = st.file_uploader(
            "Upload attendance, overtime sheet, completion report, shift report, PDF, Excel, CSV, or text",
            accept_multiple_files=True,
            type=["pdf", "xlsx", "xls", "csv", "txt", "log"],
        )

        submitted = st.form_submit_button("Submit overtime claim", type="primary")

    if submitted:
        if not employee_name.strip() or not work_description.strip():
            st.error("Employee name and work performed are required.")
            return
        payload = {
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
        }
        claim_id = create_claim(payload, files or [])
        st.success(f"Claim #{claim_id} submitted.")
        show_claim_result(claim_id)

    with st.expander("What this portal checks"):
        st.write(
            "The backend deducts lunch where applicable, compares claimed overtime with attendance-based "
            "overtime, classifies the electrical work type, checks expected duration benchmarks, extracts "
            "uploaded PDF/Excel evidence, and produces a Green/Yellow/Red recommendation."
        )


def show_claim_result(claim_id: int) -> None:
    claim = get_claim(claim_id)
    if not claim:
        return
    analysis = claim["analysis"]
    st.subheader("Verification result")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Status", analysis["status"])
    c2.metric("Risk score", analysis["risk_score"])
    c3.metric("Actual OT", f'{analysis["actual_overtime_hours"]:.2f} hr')
    c4.metric("Expected work", f'{analysis["expected_hours"]:.2f} hr')

    st.write(f"**Work type:** {analysis['work_type'].title()}")
    st.write(f"**Industry segment:** {analysis['industry_segment']}")
    st.write(f"**Recommendation:** {analysis['recommendation']}")

    if analysis["flags"]:
        st.warning("Flags generated")
        for flag in analysis["flags"]:
            st.write(f"- {flag}")
    else:
        st.success("No anomalies detected.")

    if analysis["follow_up_questions"]:
        st.info("Possible follow-up questions")
        for question in analysis["follow_up_questions"]:
            st.write(f"- {question}")

    st.text_area("AI summary", value=analysis["ai_summary"], height=120, disabled=True)


if __name__ == "__main__":
    main()
