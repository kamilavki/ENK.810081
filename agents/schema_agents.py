import pandas as pd
import re
from typing import Dict, Any, List


ALLOWED_TYPES = {"int", "float", "date", "string", "bool"}


def is_snake_case(name: str) -> bool:
    return bool(re.fullmatch(r"[a-z][a-z0-9_]*", name))


def detect_type(series: pd.Series) -> str:
    """
    Infer the most likely type of a column using non-null values.
    """
    non_null = series.dropna()

    if non_null.empty:
        return "unknown"

    # Try boolean-like
    bool_set = {True, False, "True", "False", "true", "false", 0, 1, "0", "1"}
    if non_null.isin(bool_set).all():
        return "bool"

    # Try numeric
    numeric = pd.to_numeric(non_null, errors="coerce")
    if numeric.notna().all():
        if (numeric % 1 == 0).all():
            return "int"
        return "float"

    # Try date
    dt = pd.to_datetime(non_null, errors="coerce")
    if dt.notna().all():
        return "date"

    return "string"


def get_invalid_samples(series: pd.Series, expected_type: str) -> List[Any]:
    """
    Return up to 5 invalid sample values for the expected type.
    """
    non_null = series.dropna()

    if non_null.empty:
        return []

    if expected_type == "int":
        converted = pd.to_numeric(non_null, errors="coerce")
        invalid = non_null[converted.isna()]
        if not invalid.empty:
            return invalid.head(5).tolist()

        non_integer = converted[converted % 1 != 0]
        return non_null.loc[non_integer.index].head(5).tolist()

    elif expected_type == "float":
        converted = pd.to_numeric(non_null, errors="coerce")
        invalid = non_null[converted.isna()]
        return invalid.head(5).tolist()

    elif expected_type == "date":
        converted = pd.to_datetime(non_null, errors="coerce")
        invalid = non_null[converted.isna()]
        return invalid.head(5).tolist()

    elif expected_type == "bool":
        valid_set = {True, False, "True", "False", "true", "false", 0, 1, "0", "1"}
        invalid = non_null[~non_null.isin(valid_set)]
        return invalid.head(5).tolist()

    elif expected_type == "string":
        return []

    return [f"Unsupported expected type: {expected_type}"]


def suggest_remediation(col: str, expected_type: str, invalid_samples: List[Any]) -> str:
    if expected_type == "int":
        return f"Convert `{col}` to integer; coerce non-numeric or decimal values to NULL, then impute or review manually."
    elif expected_type == "float":
        return f"Convert `{col}` to numeric/float; coerce invalid values to NULL, then fill with median or review manually."
    elif expected_type == "date":
        return f"Parse `{col}` as datetime using a consistent format; invalid date strings should be corrected or set to NULL."
    elif expected_type == "bool":
        return f"Standardize `{col}` to boolean values such as True/False or 1/0; map invalid values manually."
    elif expected_type == "string":
        return f"Cast `{col}` to string and standardize formatting if needed."
    return f"Review `{col}` manually."


def compute_schema_score(report: Dict[str, Any], total_expected_columns: int) -> float:
    """
    Very simple scoring rule for Step 1.
    Starts from 100 and subtracts penalties.
    """
    score = 100.0

    score -= 10 * len(report["missing_columns"])
    score -= 5 * len(report["unexpected_columns"])
    score -= 3 * len(report["naming_violations"])
    score -= 7 * len(report["type_issues"])

    return round(max(score, 0), 2)


def schema_validation(df: pd.DataFrame, expected_schema: Dict[str, str]) -> Dict[str, Any]:
    for col, typ in expected_schema.items():
        if typ not in ALLOWED_TYPES:
            raise ValueError(
                f"Unsupported type '{typ}' for column '{col}'. Allowed types: {sorted(ALLOWED_TYPES)}"
            )

    report = {
        "phase": "schema_validation",
        "valid": True,
        "summary": {
            "total_columns_in_dataset": len(df.columns),
            "total_expected_columns": len(expected_schema)
        },
        "missing_columns": [],
        "unexpected_columns": [],
        "naming_violations": [],
        "type_issues": {},
        "schema_score": None
    }

    actual_columns = set(df.columns)
    expected_columns = set(expected_schema.keys())

    report["missing_columns"] = sorted(list(expected_columns - actual_columns))
    report["unexpected_columns"] = sorted(list(actual_columns - expected_columns))

    for col in df.columns:
        if not is_snake_case(col):
            report["naming_violations"].append({
                "column": col,
                "suggested_name": re.sub(r"(?<!^)(?=[A-Z])", "_", col).lower().replace(" ", "_")
            })

    for col, expected_type in expected_schema.items():
        if col not in df.columns:
            continue

        detected_type = detect_type(df[col])
        invalid_samples = get_invalid_samples(df[col], expected_type)

        if invalid_samples or (detected_type != expected_type and expected_type != "string"):
            report["type_issues"][col] = {
                "expected_type": expected_type,
                "detected_type": detected_type,
                "invalid_samples": invalid_samples,
                "remediation": suggest_remediation(col, expected_type, invalid_samples)
            }

    if (
        report["missing_columns"]
        or report["unexpected_columns"]
        or report["naming_violations"]
        or report["type_issues"]
    ):
        report["valid"] = False

    report["schema_score"] = compute_schema_score(report, len(expected_schema))
    return report