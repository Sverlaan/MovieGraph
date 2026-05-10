from datetime import date, datetime
import ast
import pandas as pd
import json
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def cast_string(s: pd.Series) -> pd.Series:
    return s.astype("string")


def cast_int(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").astype("Int64")


def cast_float(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def cast_bool(s: pd.Series) -> pd.Series:
    return s.astype("boolean")


def cast_date(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce").dt.date


def cast_datetime(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce")


TYPE_CASTERS = {
    "string": cast_string,
    "integer": cast_int,
    "float": cast_float,
    "boolean": cast_bool,
    "date": cast_date,
    "datetime": cast_datetime,
}


def cast_properties_from_ontology(
    df,
    label: str,
    ontology_props: dict,
):
    df = df.copy()

    for prop, typ in ontology_props.items():
        if prop not in df.columns:
            continue

        caster = TYPE_CASTERS.get(typ)
        if not caster:
            raise ValueError(f"Unknown type '{typ}' for {label}.{prop}")

        try:
            df[prop] = caster(df[prop])
        except Exception as e:
            raise ValueError(
                f"Failed casting {label}.{prop} to {typ}"
            ) from e

    return df


def preprocess_movies(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Remove rows where columns "tmdb_id" and "imdb_id" either one are missing or empty strings

    df = df.dropna(subset=["tmdb_id", "imdb_id"], how="all")
    df = df[~((df["tmdb_id"] == "") | (df["imdb_id"] == ""))]
    df["release_date"] = pd.to_datetime(df["release_date"], errors="coerce")
    df["release_year"] = df["release_date"].dt.year.astype("Int64")
    return df


def preprocess_people(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Remove rows where "tmdb_id" is missing or empty string
    df = df.dropna(subset=["tmdb_id", "imdb_id"], how="all")
    df = df[~((df["tmdb_id"] == "") | (df["imdb_id"] == ""))]
    return df


def explode_json(df, column, id_column):
    """
    Explodes a JSON column that can be:
    - a list of objects
    - a single object
    - NULL / NaN

    Adds `order` if the column contains a list, indicating the position of each item in the original list (starting from 0).
    This can be used for example to keep only the top N cast members based on their billing order, for example.
    """
    rows = []

    for _, row in df.iterrows():
        raw = row[column]

        if pd.isna(raw):
            continue

        # Handle broken JSON
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = ast.literal_eval(raw)

        # Normalize to list
        if isinstance(parsed, dict):
            parsed = [parsed]
        elif not isinstance(parsed, list):
            continue

        for idx, item in enumerate(parsed):  # <-- capture position
            if not isinstance(item, dict):
                continue

            new_row = {id_column: row[id_column]}
            new_row.update(item)

            # billing order = position in list
            new_row["order"] = idx

            rows.append(new_row)

    return pd.DataFrame(rows)


def process_cast(cast_value, max_order=10) -> List[Dict[str, Any]]:
    # Handle NaN / empty
    # if pd.isna(cast_value):
    #     return []

    # Parse stringified list if needed
    if isinstance(cast_value, str):
        try:
            cast_list = ast.literal_eval(cast_value)
        except Exception:
            return []
    else:
        cast_list = cast_value

    if not isinstance(cast_list, list):
        return []

    return [
        {
            "id": member.get("id"),
            "name": member.get("name"),
            "character": member.get("character"),
        }
        for member in cast_list
        if isinstance(member, dict) and member.get("order", 999) < max_order
    ]


def process_crew(
    crew_value,
    allowed_jobs: set[str] = {"Director",
                              "Writer",
                              "Screenplay",
                              "Producer",
                              "Executive Producer",
                              "Director of Photography",
                              "Editor",
                              "Original Music Composer",
                              "Production Design"}
) -> List[Dict[str, Any]]:
    """
    Parse, filter, and normalize crew data.
    Keeps only crew members whose job is in allowed_jobs and
    returns only id, name, job, and department.
    """

    # Handle NaN / empty
    # if pd.isna(crew_value):
    #     return []

    # Parse stringified list if needed
    if isinstance(crew_value, str):
        try:
            crew_list = ast.literal_eval(crew_value)
        except Exception:
            return []
    else:
        crew_list = crew_value

    if not isinstance(crew_list, list):
        return []

    return [
        {
            "id": member.get("id"),
            "name": member.get("name"),
            "job": member.get("job"),
            "department": member.get("department"),
        }
        for member in crew_list
        if isinstance(member, dict)
        and member.get("job") in allowed_jobs
    ]
