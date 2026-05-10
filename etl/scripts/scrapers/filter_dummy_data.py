# This script filters the Oscars, Ratings, and Watchlists datasets to only include entries that match movies present in the movies.db SQLite database.

import sqlite3
import pandas as pd

# Paths
base_path = "etl/dummy_data/sources/"
db_path = base_path + "movies.db"

oscars_path = base_path + "oscars_normalized.csv"
ratings_path = base_path + "users/ratings.csv"
watchlists_path = base_path + "users/watchlists.csv"

oscars_output = base_path + "oscars_filtered_by_movies.csv"
ratings_output = base_path + "ratings_filtered_by_movies.csv"
watchlists_output = base_path + "watchlists_filtered_by_movies.csv"

# --- Connect to SQLite ---
conn = sqlite3.connect(db_path)

query = """
SELECT slug, imdb_id
FROM movies_v4_dummy
"""
movies_df = pd.read_sql_query(query, conn)
conn.close()

# Ensure string types for matching
movies_df["slug"] = movies_df["slug"].astype(str)
movies_df["imdb_id"] = movies_df["imdb_id"].astype(str)

# =====================================================
# 1️⃣ Filter Oscars by imdb_id
# =====================================================

oscars_df = pd.read_csv(oscars_path)
oscars_df["FilmId"] = oscars_df["FilmId"].astype(str)

oscars_filtered = oscars_df[
    oscars_df["FilmId"].isin(movies_df["imdb_id"])
]

oscars_filtered.to_csv(oscars_output, index=False)

# =====================================================
# 2️⃣ Filter Ratings by slug
# =====================================================

ratings_df = pd.read_csv(ratings_path)
ratings_df["slug"] = ratings_df["slug"].astype(str)

ratings_filtered = ratings_df[
    ratings_df["slug"].isin(movies_df["slug"])
]

ratings_filtered.to_csv(ratings_output, index=False)

# =====================================================
# 3️⃣ Filter Watchlists by slug
# =====================================================

watchlists_df = pd.read_csv(watchlists_path)
watchlists_df["slug"] = watchlists_df["slug"].astype(str)

watchlists_filtered = watchlists_df[
    watchlists_df["slug"].isin(movies_df["slug"])
]

watchlists_filtered.to_csv(watchlists_output, index=False)

# Summary
print("Filtering complete:")
print(f"Oscars rows kept: {len(oscars_filtered)}")
print(f"Ratings rows kept: {len(ratings_filtered)}")
print(f"Watchlists rows kept: {len(watchlists_filtered)}")
