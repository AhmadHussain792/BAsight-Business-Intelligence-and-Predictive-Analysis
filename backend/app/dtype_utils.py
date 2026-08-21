"""
Small dtype-detection helpers shared by ingestion and schema_detection.

Why this exists: pandas 3.x changed the default dtype for text columns
from the classic `object` dtype to a new `str` extension dtype. Code
that checks `series.dtype == object` or `pd.api.types.is_object_dtype`
silently stops matching text columns on pandas 3.x while still working
on pandas 2.x — exactly the kind of version-dependent bug that's easy
to miss in dev and hit in production. Centralizing the check here means
it only has to be fixed once.
"""
import pandas as pd


def is_textual_dtype(series: pd.Series) -> bool:
    """True for both legacy object-dtype string columns and pandas 3.x's
    dedicated string dtype. Deliberately excludes numeric/datetime/bool."""
    return bool(pd.api.types.is_string_dtype(series) or pd.api.types.is_object_dtype(series))
