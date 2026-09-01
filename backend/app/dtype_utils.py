# dtype-detection helpers shared by ingestion and schema_detection.
import pandas as pd

def is_textual_dtype(series: pd.Series) -> bool:
    return bool(pd.api.types.is_string_dtype(series) or pd.api.types.is_object_dtype(series))