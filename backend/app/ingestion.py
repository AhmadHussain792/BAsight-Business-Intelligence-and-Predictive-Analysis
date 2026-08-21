"""
File reading + cleaning. Turns raw uploaded bytes into a cleaned,
type-coerced DataFrame. This is the layer that has to survive messy
real-world SME exports: mixed encodings, currency-formatted numbers,
inconsistent date strings, stray whitespace, fully-blank rows.
"""
import csv
import io
import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import settings
from .dtype_utils import is_textual_dtype

# Encodings tried in order. latin-1 is last because it never raises
# (every byte maps to a character), so it must not be tried first or
# it would mask genuine utf-8 files.
CANDIDATE_ENCODINGS = ["utf-8-sig", "utf-8", "cp1252", "latin-1"]

CURRENCY_CHARS = "$£€¥"


@dataclass
class CleaningReport:
    original_row_count: int
    original_column_count: int
    dropped_empty_rows: int
    dropped_empty_columns: int
    renamed_duplicate_columns: list[str] = field(default_factory=list)
    columns_converted_to_numeric: list[str] = field(default_factory=list)
    columns_converted_to_datetime: list[str] = field(default_factory=list)
    date_format_notes: dict[str, str] = field(default_factory=dict)


_SLASH_DATE_PATTERN = re.compile(r"^\s*(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})\s*$")


def _detect_dayfirst(series: pd.Series, sample_size: int = 500) -> bool | None:
    """
    Numeric date strings like 05/04/2025 are ambiguous (5 April vs May
    4th) unless a value in the column breaks the tie — e.g. 13/04/2025
    can only be day-first, since no month is 13. Scans for such
    tie-breaking values. Returns True/False if the convention can be
    determined, or None if every sampled value is ambiguous (in which
    case the caller must assume and say so).
    """
    dayfirst_evidence = False
    monthfirst_evidence = False
    for value in series.dropna().astype(str).head(sample_size):
        match = _SLASH_DATE_PATTERN.match(value)
        if not match:
            continue
        first, second = int(match.group(1)), int(match.group(2))
        if first > 12:
            dayfirst_evidence = True
        if second > 12:
            monthfirst_evidence = True
    if dayfirst_evidence and not monthfirst_evidence:
        return True
    if monthfirst_evidence and not dayfirst_evidence:
        return False
    return None  # fully ambiguous, or conflicting formats mixed in one column


class UnsupportedFileError(ValueError):
    pass


class EmptyFileError(ValueError):
    pass


def _sniff_delimiter(sample_text: str) -> str:
    """Best-effort delimiter detection; falls back to comma."""
    try:
        dialect = csv.Sniffer().sniff(sample_text[:4096], delimiters=",;\t|")
        return dialect.delimiter
    except csv.Error:
        return ","


def _decode_csv_bytes(contents: bytes) -> str:
    last_error: Exception | None = None
    for encoding in CANDIDATE_ENCODINGS:
        try:
            return contents.decode(encoding)
        except (UnicodeDecodeError, LookupError) as exc:
            last_error = exc
    # latin-1 should always succeed, so this is unreachable in practice,
    # but keep an explicit failure path rather than a silent None.
    raise UnsupportedFileError(f"Could not decode file with any supported encoding: {last_error}")


def read_uploaded_file(filename: str, contents: bytes) -> pd.DataFrame:
    """
    Dispatches on file extension and returns a raw (uncleaned) DataFrame.
    Raises UnsupportedFileError / EmptyFileError on bad input.
    """
    if not contents:
        raise EmptyFileError("The uploaded file is empty.")

    lower_name = filename.lower()

    if lower_name.endswith(".csv"):
        text = _decode_csv_bytes(contents)
        if not text.strip():
            raise EmptyFileError("The uploaded CSV has no content.")
        delimiter = _sniff_delimiter(text)
        try:
            df = pd.read_csv(io.StringIO(text), sep=delimiter, engine="python")
        except Exception as exc:  # pandas raises many different error types here
            raise UnsupportedFileError(f"Could not parse CSV: {exc}") from exc

    elif lower_name.endswith((".xlsx", ".xls")):
        try:
            df = pd.read_excel(io.BytesIO(contents))
        except Exception as exc:
            raise UnsupportedFileError(f"Could not parse Excel file: {exc}") from exc

    else:
        raise UnsupportedFileError(
            f"Unsupported file type. Allowed: {', '.join(sorted(settings.ALLOWED_EXTENSIONS))}"
        )

    if df.shape[1] == 0:
        raise EmptyFileError("No columns could be detected in the uploaded file.")

    return df


def _dedupe_column_names(columns: list[str]) -> tuple[list[str], list[str]]:
    """Appends a numeric suffix to any repeated column name so nothing
    is silently overwritten downstream."""
    seen: dict[str, int] = {}
    renamed: list[str] = []
    result: list[str] = []
    for col in columns:
        clean = str(col).strip() or "unnamed_column"
        if clean in seen:
            seen[clean] += 1
            new_name = f"{clean}_{seen[clean]}"
            renamed.append(new_name)
        else:
            seen[clean] = 0
            new_name = clean
        result.append(new_name)
    return result, renamed


def _try_convert_numeric(series: pd.Series) -> pd.Series | None:
    """Strips currency symbols/commas/percent signs and attempts numeric
    conversion. Returns the converted series if enough values survive,
    else None."""
    if pd.api.types.is_numeric_dtype(series):
        return None  # already numeric, nothing to do

    non_null = series.dropna()
    if non_null.empty:
        return None

    cleaned = (
        series.astype(str)
        .str.strip()
        .str.replace(f"[{CURRENCY_CHARS}]", "", regex=True)
        .str.replace(",", "", regex=False)
        .str.replace("%", "", regex=False)
        .str.replace(r"^\((.*)\)$", r"-\1", regex=True)  # accounting negatives: (12.5) -> -12.5
    )
    converted = pd.to_numeric(cleaned, errors="coerce")

    success_rate = converted.notna().sum() / len(non_null)
    if success_rate >= settings.NUMERIC_CONVERSION_THRESHOLD:
        # Preserve original nulls rather than the string "nan" artifacts.
        converted[series.isna()] = np.nan
        return converted
    return None


def _try_convert_datetime(series: pd.Series) -> tuple[pd.Series, str | None] | None:
    """Returns (converted_series, note) on success, where note is a
    human-readable string only when the day-first/month-first
    convention had to be assumed rather than detected; None on failure."""
    if pd.api.types.is_datetime64_any_dtype(series):
        return None
    if pd.api.types.is_numeric_dtype(series):
        return None  # avoid turning plain integers/prices into epoch dates

    non_null = series.dropna()
    if non_null.empty:
        return None

    dayfirst_detected = _detect_dayfirst(series)
    dayfirst = dayfirst_detected if dayfirst_detected is not None else True

    converted = pd.to_datetime(series, errors="coerce", dayfirst=dayfirst, format="mixed")
    success_rate = converted.notna().sum() / len(non_null)
    if success_rate < settings.DATE_CONVERSION_THRESHOLD:
        return None

    note = None
    if dayfirst_detected is None:
        note = (
            "Date format was ambiguous (e.g. 04/05/2025) — assumed day-first "
            "(DD/MM/YYYY). Verify this matches your source data."
        )
    return converted, note


def clean_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, CleaningReport]:
    """
    Applies the cleaning pipeline and returns the cleaned frame plus a
    report describing what was changed, so the API can surface it
    instead of cleaning silently.
    """
    original_rows, original_cols = df.shape

    df = df.copy()
    new_columns, renamed = _dedupe_column_names(list(df.columns))
    df.columns = new_columns

    # Drop rows/columns that are entirely empty.
    df = df.dropna(axis=0, how="all")
    df = df.dropna(axis=1, how="all")
    dropped_rows = original_rows - df.shape[0]
    dropped_cols = original_cols - df.shape[1]

    # Strip whitespace on text columns (covers both legacy object dtype
    # and pandas 3.x's dedicated string dtype — see dtype_utils).
    text_cols = [c for c in df.columns if is_textual_dtype(df[c])]
    for col in text_cols:
        df[col] = df[col].apply(lambda v: v.strip() if isinstance(v, str) else v)
        df[col] = df[col].replace({"": np.nan, "nan": np.nan, "NaN": np.nan, "null": np.nan, "N/A": np.nan})

    numeric_converted: list[str] = []
    datetime_converted: list[str] = []
    date_format_notes: dict[str, str] = {}

    for col in df.columns:
        if not is_textual_dtype(df[col]):
            continue

        datetime_result = _try_convert_datetime(df[col])
        if datetime_result is not None:
            converted, note = datetime_result
            df[col] = converted
            datetime_converted.append(col)
            if note:
                date_format_notes[col] = note
            continue

        as_numeric = _try_convert_numeric(df[col])
        if as_numeric is not None:
            df[col] = as_numeric
            numeric_converted.append(col)

    report = CleaningReport(
        original_row_count=original_rows,
        original_column_count=original_cols,
        dropped_empty_rows=dropped_rows,
        dropped_empty_columns=dropped_cols,
        renamed_duplicate_columns=renamed,
        columns_converted_to_numeric=numeric_converted,
        columns_converted_to_datetime=datetime_converted,
        date_format_notes=date_format_notes,
    )
    return df, report
