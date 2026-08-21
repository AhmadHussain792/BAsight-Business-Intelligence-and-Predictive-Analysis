import pandas as pd
import numpy as np
from typing import Dict, Any

class DataProfiler:
    """
    Handles data ingestion, schema profiling, and server-side metric computation.
    This replaces basic row/column counting with a robust schema contract.
    """

    def profile_dataframe(df: pd.DataFrame):
        """
        Analyzes the dataframe to infer column types, missing values, and cardinality.
        Returns a structured JSON schema contract.
        """
        schema = {}
        
        for col in df.columns:
            col_data = df[col]
            dtype = str(col_data.dtype)
            
            # 1. Infer semantic type beyond basic pandas dtypes
            inferred_type = "unknown"
            if pd.api.types.is_numeric_dtype(col_data):
                inferred_type = "numeric"
            elif pd.api.types.is_datetime64_any_dtype(col_data):
                inferred_type = "datetime"
            else:
                inferred_type = "categorical"
                # Fallback date detection based on column name and string format
                if "date" in col.lower() or "time" in col.lower():
                    try:
                        # Test if it can be converted to datetime
                        pd.to_datetime(col_data.dropna().head(10))
                        inferred_type = "datetime"
                    except:
                        pass
            
            # 2. Calculate missing values and cardinality
            null_count = int(col_data.isnull().sum())
            null_percentage = round((null_count / len(df)) * 100, 2)
            cardinality = int(col_data.nunique())
            
            # 3. Get sample values (safely drop NAs first)
            valid_data = col_data.dropna()
            samples = valid_data.head(3).tolist() if not valid_data.empty else []
            
            schema[col] = {
                "pandas_dtype": dtype,
                "inferred_type": inferred_type,
                "null_percentage": null_percentage,
                "cardinality": cardinality,
                "samples": samples
            }
            
        return {
            "total_rows": len(df),
            "total_columns": len(df.columns),
            "columns": schema
        }

    def generate_insights(df: pd.DataFrame, schema: Dict[str, Any]):
        """
        Computes standard business metrics server-side based on the inferred schema.
        Returns clean JSON for Recharts to consume.
        """
        insights = {
            "top_level_metrics": {},
            "charts": {}
        }
        
        # 1. Find key columns based on the schema
        numeric_cols = [col for col, meta in schema["columns"].items() if meta["inferred_type"] == "numeric"]
        cat_cols = [col for col, meta in schema["columns"].items() if meta["inferred_type"] == "categorical"]
        date_cols = [col for col, meta in schema["columns"].items() if meta["inferred_type"] == "datetime"]
        
        # 2. Top-level metric: Total sum of the first numeric column (e.g., Revenue/Sales)
        if numeric_cols:
            primary_metric = numeric_cols[0]
            insights["top_level_metrics"]["primary_total"] = {
                "label": f"Total {primary_metric}",
                "value": float(df[primary_metric].sum())
            }
            
        # 3. Chart Data: Top N Categories
        if cat_cols and numeric_cols:
            primary_cat = cat_cols[0]
            primary_metric = numeric_cols[0]
            
            # Group by category, sum the metric, sort, and take top 5
            top_cats = df.groupby(primary_cat)[primary_metric].sum().nlargest(5).reset_index()
            insights["charts"]["category_breakdown"] = {
                "title": f"Top 5 {primary_cat} by {primary_metric}",
                "data": top_cats.to_dict(orient="records") # Ready for Recharts
            }
            
        return insights