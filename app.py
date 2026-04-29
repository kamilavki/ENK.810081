
import json
import re
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st


# =========================
# Page configuration
# =========================

st.set_page_config(
    page_title="AI Agents for Data Quality",
    page_icon="🧪",
    layout="wide"
)


# =========================
# Utilities
# =========================

def load_dataset(csv_path):
    df = pd.read_csv(csv_path)
    return {
        "df": df,
        "columns": list(df.columns),
        "shape": df.shape,
        "dtypes": df.dtypes.astype(str).to_dict()
    }


def check_naming_conventions(columns):
    issues = []
    for col in columns:
        if col.strip() != col:
            issues.append(f"'{col}' has leading/trailing spaces")
        if re.search(r"[^0-9a-zA-Z_]", col):
            issues.append(f"'{col}' has special characters")
        if len(col) > 0 and col[0].isdigit():
            issues.append(f"'{col}' starts with a digit")
    return issues


def detect_data_type_issues(df):
    issues = []
    type_info = {}

    for col in df.columns:
        series = df[col]

        if series.isna().all():
            type_info[col] = "unknown"
            continue

        numeric_mask = pd.to_numeric(series, errors="coerce").notna()
        numeric_count = numeric_mask.sum()
        total_non_missing = series.notna().sum()

        if total_non_missing == 0:
            type_info[col] = "unknown"
            continue

        ratio = numeric_count / total_non_missing

        if ratio >= 0.8:
            type_info[col] = "numeric"
            if numeric_count < total_non_missing:
                bad = series[~numeric_mask & series.notna()].unique()[:5]
                issues.append(f"'{col}' is mostly numeric but has non-numeric values: {list(bad)}")
        else:
            type_info[col] = "string"
            if numeric_count > 0:
                bad = series[numeric_mask].unique()[:5]
                issues.append(f"'{col}' is mostly strings but has numeric values: {list(bad)}")

    return issues, type_info


# =========================
# Agents
# =========================

def schema_agent(csv_path):
    meta = load_dataset(csv_path)
    df = meta["df"]
    columns = meta["columns"]

    naming_issues = check_naming_conventions(columns)
    dtype_issues, inferred_types = detect_data_type_issues(df)

    total_issues = len(naming_issues) + len(dtype_issues)
    score = max(100 - 5 * total_issues, 0)

    return {
        "naming_issues": naming_issues,
        "data_type_issues": dtype_issues,
        "inferred_types": inferred_types,
        "schema_score": round(score, 2)
    }


def completeness_agent(csv_path):
    meta = load_dataset(csv_path)
    df = meta["df"].copy()

    placeholders = ["", " ", "NA", "N/A", "na", "n/a", "unknown", "Unknown", "-", "--", "null", "NULL", "None"]

    df_normalized = df.replace(placeholders, np.nan)

    per_column = {}
    total_cells = df_normalized.shape[0] * df_normalized.shape[1]
    total_missing = int(df_normalized.isna().sum().sum())

    for col in df_normalized.columns:
        missing_count = int(df_normalized[col].isna().sum())
        completeness_pct = round(100 * (1 - missing_count / len(df_normalized)), 2) if len(df_normalized) else 100
        per_column[col] = {
            "missing_count": missing_count,
            "completeness_pct": completeness_pct
        }

    row_missing_counts = df_normalized.isna().sum(axis=1)
    rows_with_missing = row_missing_counts[row_missing_counts > 0].to_dict()

    sparse_columns = [
        col for col, stats in per_column.items()
        if stats["completeness_pct"] < 50
    ]

    overall_completeness = round(100 * (1 - total_missing / total_cells), 2) if total_cells else 100

    return {
        "per_column_completeness": per_column,
        "total_missing_values": total_missing,
        "rows_with_missing": rows_with_missing,
        "sparse_columns": sparse_columns,
        "completeness_score": overall_completeness
    }


def consistency_agent(csv_path):
    meta = load_dataset(csv_path)
    df = meta["df"]

    duplicate_mask = df.duplicated(keep="first")
    duplicate_indices = df.index[duplicate_mask].tolist()
    duplicate_rows = int(duplicate_mask.sum())

    format_issues = []
    for col in df.select_dtypes(include=["object"]).columns:
        unique_original = set(df[col].dropna().astype(str).unique())
        unique_lower = set(df[col].dropna().astype(str).str.lower().unique())

        if len(unique_lower) < len(unique_original):
            format_issues.append(f"'{col}' has inconsistent casing: {list(unique_original)[:5]}")

    cross_column_issues = []

    # Specific format consistency check for NoiPA-style period column.
    if "Rata" in df.columns:
        for idx, value in df["Rata"].dropna().items():
            value_str = str(int(value)) if isinstance(value, (int, float, np.integer, np.floating)) else str(value)
            if not (value_str.isdigit() and len(value_str) == 6):
                cross_column_issues.append(f"row {idx}: Rata='{value}' not in YYYYMM format")

    # Generic cross-column consistency check.
    checked_pairs = set()
    max_cross_column_issues = 50

    for col1 in df.columns:
        for col2 in df.columns:
            if col1 == col2:
                continue

            if (col2, col1) in checked_pairs:
                continue
            checked_pairs.add((col1, col2))

            s1 = df[col1].dropna()

            # col1 must be low-cardinality to behave like a key/category.
            if s1.nunique() > 20:
                continue

            pairs = df[[col1, col2]].dropna()

            if len(pairs) < 5:
                continue

            mapping = pairs.groupby(col1)[col2].nunique()
            mostly_one_to_one = (mapping == 1).mean() >= 0.80
            inconsistent_keys = mapping[mapping > 1]

            if mostly_one_to_one and len(inconsistent_keys) > 0:
                for key in inconsistent_keys.index:
                    if len(cross_column_issues) >= max_cross_column_issues:
                        break

                    vals = pairs[pairs[col1] == key][col2].unique()
                    cross_column_issues.append(
                        f"'{col1}'='{key}' maps to {len(vals)} different '{col2}' values: {list(vals[:3])}"
                    )

            if len(cross_column_issues) >= max_cross_column_issues:
                break

        if len(cross_column_issues) >= max_cross_column_issues:
            break

    duplicate_penalty = min(30, duplicate_rows * 0.5)
    format_penalty = min(30, len(format_issues) * 5)
    cross_column_penalty = min(40, len(cross_column_issues) * 2)

    total_penalty = duplicate_penalty + format_penalty + cross_column_penalty
    score = round(max(100 - total_penalty, 0), 2)

    return {
        "duplicate_rows": duplicate_rows,
        "duplicate_indices": duplicate_indices[:100],
        "format_issues": format_issues,
        "cross_column_issues": cross_column_issues,
        "consistency_score": score
    }


def anomaly_agent(csv_path):
    meta = load_dataset(csv_path)
    df = meta["df"]

    numerical_outliers = {}
    categorical_anomalies = []
    total_outliers = 0

    id_like_keywords = ["id", "_id", "codice", "code", "cf", "tax", "uuid"]

    def is_identifier_column(col, series):
        col_lower = str(col).lower()

        if any(key in col_lower for key in id_like_keywords):
            return True

        non_null = series.dropna()

        if len(non_null) == 0:
            return False

        # In tiny datasets, almost every column looks unique.
        # Only use uniqueness ratio as an ID signal for larger columns.
        if len(non_null) < 20:
            return False

        uniqueness_ratio = non_null.nunique() / len(non_null)
        return uniqueness_ratio > 0.80

    # Numerical outlier detection.
    for col in df.columns:
        if is_identifier_column(col, df[col]):
            continue

        numeric_series = pd.to_numeric(df[col], errors="coerce").dropna()

        if len(numeric_series) < 2:
            continue

        series = numeric_series
        mean, std = series.mean(), series.std()

        if len(series) < 10:
            median = series.median()

            if median > 0:
                outlier_mask = (series > median * 10) | (series < median / 10)
            else:
                deviations = (series - median).abs()
                outlier_mask = deviations > 10 * max(deviations.median(), 1)
        else:
            if std == 0 or np.isnan(std):
                continue

            z_scores = (series - mean) / std
            outlier_mask = z_scores.abs() > 3

        outlier_indices = series.index[outlier_mask].tolist()
        count = len(outlier_indices)

        total_outliers += count

        if count > 0:
            numerical_outliers[col] = {
                "mean": round(float(mean), 2),
                "std": round(float(std), 2) if not np.isnan(std) else None,
                "outlier_count": int(count),
                "outlier_indices": outlier_indices[:20],
                "note": "Only the first 20 outlier indices are shown."
            }

    # Categorical anomaly detection.
    for col in df.select_dtypes(include=["object"]).columns:
        series = df[col]

        if is_identifier_column(col, series):
            continue

        non_null = series.dropna()

        if len(non_null) == 0:
            continue

        unique_count = non_null.nunique()
        uniqueness_ratio = unique_count / len(non_null)

        # Skip high-cardinality columns to avoid noisy reports.
        if unique_count > 50 or uniqueness_ratio > 0.30:
            continue

        value_counts = non_null.value_counts()
        total = value_counts.sum()

        rare = value_counts[value_counts / total < 0.01]

        for val, count in rare.items():
            categorical_anomalies.append({
                "column": col,
                "value": str(val),
                "count": int(count),
                "message": f"'{col}': rare value '{val}' appears {int(count)} time(s)"
            })

    anomaly_penalty = min(60, 2 * total_outliers + 5 * len(categorical_anomalies))
    score = round(max(100 - anomaly_penalty, 0), 2)

    return {
        "numerical_outliers": numerical_outliers,
        "categorical_anomalies": categorical_anomalies[:100],
        "anomaly_score": score
    }


def remediation_agent(results):
    schema = results.get("schema", {})
    completeness = results.get("completeness", {})
    consistency = results.get("consistency", {})
    anomaly = results.get("anomaly", {})

    suggestions = []

    for issue in schema.get("naming_issues", []):
        col_name = issue.split("'")[1] if "'" in issue else "column"
        if "spaces" in issue:
            suggestions.append(f"Rename '{col_name}' to remove whitespace.")
        if "special characters" in issue:
            suggestions.append(f"Rename '{col_name}' using only letters, numbers, and underscores.")
        if "starts with a digit" in issue:
            suggestions.append(f"Rename '{col_name}' so it does not start with a digit.")

    for issue in schema.get("data_type_issues", []):
        col_name = issue.split("'")[1] if "'" in issue else "column"
        if "mostly numeric" in issue:
            suggestions.append(f"Convert '{col_name}' to numeric and inspect non-numeric values.")
        if "mostly strings" in issue:
            suggestions.append(f"Standardize '{col_name}' so values use one consistent type.")

    for col, stats in completeness.get("per_column_completeness", {}).items():
        if stats["completeness_pct"] < 100:
            missing_pct = 100 - stats["completeness_pct"]
            suggestions.append(f"'{col}' has {missing_pct:.2f}% missing values. Consider median/mode imputation or row filtering.")

    for col in completeness.get("sparse_columns", []):
        suggestions.append(f"'{col}' is more than 50% empty. Consider dropping it or investigating the source.")

    if consistency.get("duplicate_rows", 0) > 0:
        suggestions.append(f"Remove {consistency['duplicate_rows']} duplicate rows.")

    for issue in consistency.get("format_issues", []):
        col_name = issue.split("'")[1] if "'" in issue else "column"
        suggestions.append(f"Standardize casing and formatting in '{col_name}'.")

    for issue in consistency.get("cross_column_issues", []):
        suggestions.append(f"{issue}. Check whether this relationship is valid.")

    for col, info in anomaly.get("numerical_outliers", {}).items():
        suggestions.append(f"'{col}' has {info['outlier_count']} numerical outlier(s). Investigate and consider capping or correction.")

    for issue in anomaly.get("categorical_anomalies", []):
        msg = issue["message"] if isinstance(issue, dict) and "message" in issue else str(issue)
        suggestions.append(f"{msg}. Check whether this is valid or a data-entry error.")

    suggestions = list(dict.fromkeys(suggestions))

    schema_score = schema.get("schema_score", 50)
    completeness_score = completeness.get("completeness_score", 50)
    consistency_score = consistency.get("consistency_score", 50)
    anomaly_score = anomaly.get("anomaly_score", 50)

    reliability_score = round(
        0.2 * schema_score +
        0.3 * completeness_score +
        0.3 * consistency_score +
        0.2 * anomaly_score,
        2
    )

    summary_parts = []

    if schema.get("naming_issues") or schema.get("data_type_issues"):
        summary_parts.append("Schema issues were detected, mainly related to column names or data types.")

    if completeness.get("total_missing_values", 0) > 0:
        summary_parts.append("The dataset contains missing values across one or more columns.")

    if consistency.get("duplicate_rows", 0) > 0 or consistency.get("format_issues") or consistency.get("cross_column_issues"):
        summary_parts.append("Consistency problems were identified, including duplicates, formatting issues, or cross-column inconsistencies.")

    if anomaly.get("numerical_outliers") or anomaly.get("categorical_anomalies"):
        summary_parts.append("Anomalies were detected, such as numerical outliers or rare categorical values.")

    if not summary_parts:
        summary_parts.append("The dataset appears clean with no major data quality issues.")

    summary = " ".join(summary_parts)

    return {
        "suggestions": suggestions,
        "reliability_score": reliability_score,
        "summary": summary
    }


def fix_dataset(df, results):
    df_clean = df.copy()

    df_clean = df_clean.drop_duplicates(keep="first").reset_index(drop=True)

    sparse_cols = results.get("completeness", {}).get("sparse_columns", [])
    df_clean = df_clean.drop(columns=[c for c in sparse_cols if c in df_clean.columns], errors="ignore")

    inferred = results.get("schema", {}).get("inferred_types", {})

    for col, typ in inferred.items():
        if typ == "numeric" and col in df_clean.columns:
            df_clean[col] = pd.to_numeric(df_clean[col], errors="coerce")

    for col in df_clean.columns:
        if pd.api.types.is_numeric_dtype(df_clean[col]):
            median = df_clean[col].median()
            df_clean[col] = df_clean[col].fillna(median)
        else:
            mode = df_clean[col].mode(dropna=True)
            df_clean[col] = df_clean[col].fillna(mode[0] if not mode.empty else "")

    for col in df_clean.select_dtypes(include=["object"]).columns:
        df_clean[col] = df_clean[col].astype(str).str.strip().str.title()

    for col in df_clean.select_dtypes(include=[np.number]).columns:
        mean, std = df_clean[col].mean(), df_clean[col].std()
        if std > 0:
            df_clean[col] = df_clean[col].clip(mean - 3 * std, mean + 3 * std)

    return df_clean


def run_pipeline(csv_path):
    results = {}

    results["schema"] = schema_agent(csv_path)
    results["completeness"] = completeness_agent(csv_path)
    results["consistency"] = consistency_agent(csv_path)
    results["anomaly"] = anomaly_agent(csv_path)

    remediation = remediation_agent(results)
    results["remediation"] = remediation
    results["reliability_score"] = remediation["reliability_score"]

    df_original = load_dataset(csv_path)["df"]
    results["cleaned_df"] = fix_dataset(df_original, results)

    return results


# =========================
# Interface helpers
# =========================

def score_band(score):
    if score >= 80:
        return "High quality"
    if score >= 60:
        return "Acceptable, but needs fixes"
    if score >= 40:
        return "Problematic"
    return "Critical"


def make_score_table(results):
    return pd.DataFrame([
        {"Agent": "Schema", "Score": results["schema"]["schema_score"]},
        {"Agent": "Completeness", "Score": results["completeness"]["completeness_score"]},
        {"Agent": "Consistency", "Score": results["consistency"]["consistency_score"]},
        {"Agent": "Anomaly", "Score": results["anomaly"]["anomaly_score"]},
        {"Agent": "Final reliability", "Score": results["reliability_score"]},
    ])


def make_json_safe(obj):
    if isinstance(obj, pd.DataFrame):
        return obj.to_dict(orient="records")
    if isinstance(obj, dict):
        return {k: make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [make_json_safe(v) for v in obj]
    if isinstance(obj, (np.integer, np.floating)):
        return obj.item()
    return obj


# =========================
# Streamlit UI
# =========================

st.title("AI Agents for Data Quality")
st.caption("Upload a CSV file. The system runs Schema, Completeness, Consistency, Anomaly, and Remediation agents.")

uploaded_file = st.file_uploader("Upload a CSV dataset", type=["csv"])

with st.sidebar:
    st.header("How to use")
    st.write("1. Upload a CSV file.")
    st.write("2. Click **Run data quality analysis**.")
    st.write("3. Read the scores, issues, and suggestions.")
    st.write("4. Download the cleaned dataset or JSON report.")

if uploaded_file is None:
    st.info("Upload a CSV file to start.")
    st.stop()

with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
    tmp.write(uploaded_file.getvalue())
    csv_path = tmp.name

df_preview = pd.read_csv(csv_path)

st.subheader("Dataset preview")
st.write(f"Rows: **{df_preview.shape[0]}** | Columns: **{df_preview.shape[1]}**")
st.dataframe(df_preview.head(20), use_container_width=True)

if st.button("Run data quality analysis", type="primary"):
    with st.spinner("Running the agents..."):
        results = run_pipeline(csv_path)

    st.success("Analysis completed.")

    reliability = results["reliability_score"]

    st.subheader("Final reliability score")
    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric("Final", reliability)
    c2.metric("Schema", results["schema"]["schema_score"])
    c3.metric("Completeness", results["completeness"]["completeness_score"])
    c4.metric("Consistency", results["consistency"]["consistency_score"])
    c5.metric("Anomaly", results["anomaly"]["anomaly_score"])

    st.write(f"Interpretation: **{score_band(reliability)}**")

    st.subheader("Score breakdown")
    score_table = make_score_table(results)
    st.dataframe(score_table, use_container_width=True)
    st.bar_chart(score_table.set_index("Agent"))

    st.subheader("Report summary")
    st.write(results["remediation"]["summary"])

    st.subheader("Agent details")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Schema Agent",
        "Completeness Agent",
        "Consistency Agent",
        "Anomaly Agent",
        "Remediation Agent"
    ])

    with tab1:
        st.write("Checks column naming and data type consistency.")
        st.write("Naming issues:")
        st.json(results["schema"]["naming_issues"])
        st.write("Data type issues:")
        st.json(results["schema"]["data_type_issues"])
        st.write("Inferred types:")
        st.json(results["schema"]["inferred_types"])

    with tab2:
        st.write("Checks missing values, placeholder values, and sparse columns.")
        st.metric("Total missing values", results["completeness"]["total_missing_values"])

        completeness_df = pd.DataFrame.from_dict(
            results["completeness"]["per_column_completeness"],
            orient="index"
        ).reset_index().rename(columns={"index": "Column"})

        st.dataframe(completeness_df, use_container_width=True)

        st.write("Sparse columns:")
        st.json(results["completeness"]["sparse_columns"])

    with tab3:
        st.write("Checks duplicates, casing/format issues, and generic cross-column inconsistencies.")
        st.metric("Duplicate rows", results["consistency"]["duplicate_rows"])

        st.write("Duplicate row indices:")
        st.json(results["consistency"]["duplicate_indices"])

        st.write("Format issues:")
        st.json(results["consistency"]["format_issues"])

        st.write("Cross-column issues:")
        st.json(results["consistency"]["cross_column_issues"])

    with tab4:
        st.write("Checks numerical outliers and rare categorical values.")
        st.write("Numerical outliers:")
        st.json(results["anomaly"]["numerical_outliers"])

        st.write("Categorical anomalies:")
        st.json(results["anomaly"]["categorical_anomalies"])

    with tab5:
        st.write("Aggregates all findings and proposes fixes.")
        suggestions = results["remediation"]["suggestions"]

        if suggestions:
            for i, suggestion in enumerate(suggestions[:100], start=1):
                st.write(f"{i}. {suggestion}")

            if len(suggestions) > 100:
                st.info(f"Showing first 100 suggestions out of {len(suggestions)}.")
        else:
            st.write("No remediation suggestions were generated.")

    st.subheader("Cleaned dataset preview")
    cleaned_df = results["cleaned_df"]
    st.dataframe(cleaned_df.head(20), use_container_width=True)

    cleaned_csv = cleaned_df.to_csv(index=False).encode("utf-8")
    json_report = json.dumps(
        make_json_safe({k: v for k, v in results.items() if k != "cleaned_df"}),
        indent=2,
        ensure_ascii=False
    ).encode("utf-8")

    col_a, col_b = st.columns(2)

    with col_a:
        st.download_button(
            "Download cleaned CSV",
            data=cleaned_csv,
            file_name="cleaned_dataset.csv",
            mime="text/csv"
        )

    with col_b:
        st.download_button(
            "Download JSON report",
            data=json_report,
            file_name="data_quality_report.json",
            mime="application/json"
        )
