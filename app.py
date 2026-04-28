import streamlit as st
import pandas as pd
import json
from agents.schema_agent import schema_validation

st.set_page_config(page_title="Data Quality MAS - Step 1", layout="wide")

st.title("Data Quality MAS")
st.subheader("Step 1 - Schema Validation")

st.write("Upload a CSV or JSON dataset and validate it against the expected schema.")

# Load expected schema
try:
    with open("schema.json", "r", encoding="utf-8") as f:
        expected_schema = json.load(f)
except FileNotFoundError:
    st.error("schema.json not found in the project root.")
    st.stop()
except json.JSONDecodeError:
    st.error("schema.json is not a valid JSON file.")
    st.stop()

st.markdown("### Expected Schema")
st.json(expected_schema)

uploaded_file = st.file_uploader("Upload dataset", type=["csv", "json"])

if uploaded_file is not None:
    file_name = uploaded_file.name.lower()

    try:
        if file_name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        elif file_name.endswith(".json"):
            df = pd.read_json(uploaded_file)
        else:
            st.error("Unsupported file format.")
            st.stop()

        st.markdown("### Dataset Preview")
        st.dataframe(df.head())

        report = schema_validation(df, expected_schema)

        st.markdown("### Validation Result")

        col1, col2 = st.columns(2)
        with col1:
            if report["valid"]:
                st.success("Schema validation passed")
            else:
                st.warning("Schema validation found issues")

        with col2:
            st.metric("Schema Score", f"{report['schema_score']}/100")

        st.markdown("### Full Report")
        st.json(report)

        st.markdown("### Human-Readable Summary")

        if report["missing_columns"]:
            st.write("**Missing columns**")
            for col in report["missing_columns"]:
                st.write(f"- `{col}`")

        if report["unexpected_columns"]:
            st.write("**Unexpected columns**")
            for col in report["unexpected_columns"]:
                st.write(f"- `{col}`")

        if report["naming_violations"]:
            st.write("**Naming violations**")
            for item in report["naming_violations"]:
                st.write(
                    f"- `{item['column']}` should be renamed to `{item['suggested_name']}`"
                )

        if report["type_issues"]:
            st.write("**Type issues**")
            for col, issue in report["type_issues"].items():
                st.write(f"- `{col}`")
                st.write(f"  - Expected type: `{issue['expected_type']}`")
                st.write(f"  - Detected type: `{issue['detected_type']}`")
                st.write(f"  - Invalid samples: `{issue['invalid_samples']}`")
                st.write(f"  - Remediation: {issue['remediation']}")

        if (
            not report["missing_columns"]
            and not report["unexpected_columns"]
            and not report["naming_violations"]
            and not report["type_issues"]
        ):
            st.info("No schema issues were detected.")

    except Exception as e:
        st.error(f"Error while reading or validating the file: {e}")