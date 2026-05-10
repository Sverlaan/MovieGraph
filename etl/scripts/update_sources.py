from pathlib import Path
import logging
import pandas as pd
import os
from dotenv import load_dotenv
import yaml
from etl.src.clients.letterboxd_client import LetterboxdClient
from etl.src.clients.sql_client import (
    SQLiteClient,
    MoviesRepository,
    PeopleRepository,
)
from tqdm import tqdm

# ---- LOGGING ----
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---- CONFIG ----
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

USERNAMES = config["users"]["usernames"]

# ---- CREDENTIALS ----
ENV_FILE = "credentials.env"
if os.path.exists(ENV_FILE):
    load_dotenv(ENV_FILE, override=True)
    TMDB_API_KEY = os.getenv("TMDB_API_KEY")
else:
    raise FileNotFoundError(
        f"Environment file {ENV_FILE} not found. Please create it."
    )

# ---- DATABASE ----
MOVIES_SOURCE = "etl/data/sources/movies.db"
db = SQLiteClient(MOVIES_SOURCE)

movies_table_name = "movies_v5"
people_table_name = "people_v5"
movies_repo = MoviesRepository(db, movies_table_name)
people_repo = PeopleRepository(db, people_table_name)

movies_repo.create_table()
people_repo.create_table()

# ---- CLIENT ----
letterboxd_client = LetterboxdClient(tmdb_api_key=TMDB_API_KEY)

SHOW_PROGRESS_BAR = True


def main():
    # ---------------------------------------------------------
    # 1️⃣ FETCH USER DATA
    # ---------------------------------------------------------
    ratings_df, watchlists_df, users_df, diary_df = letterboxd_client.fetch_users_data(USERNAMES)
    # trending_df = letterboxd_client.get_trending_movies()

    USERS_SOURCE = Path("etl/data/sources/users")

    # Create directory if it doesn't exist
    USERS_SOURCE.mkdir(parents=True, exist_ok=True)

    logger.info("Saving user data CSVs...")

    ratings_df.to_csv(USERS_SOURCE / "ratings.csv", index=False)
    watchlists_df.to_csv(USERS_SOURCE / "watchlists.csv", index=False)
    users_df.to_csv(USERS_SOURCE / "users.csv", index=False)
    diary_df.to_csv(USERS_SOURCE / "diary.csv", index=False)
    # trending_df.to_csv(Path("etl/data/sources") / "trending.csv", index=False)

    all_user_slugs = set(ratings_df["slug"]).union(
        set(watchlists_df["slug"])
    )  # .union(set(trending_df["slug"]))

    logger.info(f"Collected {len(all_user_slugs)} unique movie slugs.")

    # ---------------------------------------------------------
    # 2️⃣ CHECK WHICH MOVIES ARE MISSING
    # ---------------------------------------------------------
    existing_movies = db.fetchall(f"SELECT slug FROM {movies_table_name}")
    slugs_in_db = {row[0] for row in existing_movies}

    slugs_to_fetch = sorted(all_user_slugs - slugs_in_db)

    logger.info(f"{len(slugs_to_fetch)} new movies to fetch.")
    if len(slugs_to_fetch) > 0:
        logger.info(f"Example slugs to fetch: {slugs_to_fetch[:25]}")

    # ---------------------------------------------------------
    # 3️⃣ FETCH & INSERT NEW MOVIES
    # ---------------------------------------------------------
    movie_rows = []

    for slug in tqdm(slugs_to_fetch, disable=not SHOW_PROGRESS_BAR):
        movie_data = letterboxd_client.fetch_movie_data(slug)

        movie_rows.append((
            movie_data["slug"],
            movie_data["lb_title"],
            movie_data["lb_year"],
            movie_data["lb_rating"],
            movie_data["lb_watchers"],
            movie_data["lb_runtime"],
            movie_data["lb_plot"],
            movie_data["lb_tagline"],
            movie_data["lb_trailer"],
            movie_data["lb_poster"],
            movie_data["lb_banner"],

            db.jdump(movie_data.get("lb_studios")),
            db.jdump(movie_data.get("lb_countries")),
            db.jdump(movie_data.get("lb_languages")),
            db.jdump(movie_data.get("lb_actor_slugs")),
            db.jdump(movie_data.get("lb_director_slugs")),
            db.jdump(movie_data.get("lb_genres")),
            db.jdump(movie_data.get("lb_themes")),
            db.jdump(movie_data.get("lb_mini_themes")),

            movie_data.get("lb_tmdb_id"),
            movie_data.get("lb_imdb_id"),
            movie_data["lb_letterboxd_id"],

            movie_data.get("lb_tmdb_url"),
            movie_data.get("lb_imdb_url"),
            movie_data["lb_letterboxd_url"],

            db.jdump(movie_data.get("belongs_to_collection")),
            movie_data.get("budget"),
            movie_data.get("status"),
            movie_data.get("homepage"),
            movie_data.get("overview"),
            movie_data.get("original_language"),
            movie_data.get("original_title"),
            movie_data.get("popularity"),
            movie_data.get("release_date"),
            movie_data.get("revenue"),

            db.jdump(movie_data.get("cast")),
            db.jdump(movie_data.get("crew")),
            db.jdump(movie_data.get("keywords")),

            movie_data.get("runtime"),
            movie_data.get("tmdb_id"),
            movie_data.get("imdb_id"),
            movie_data.get("tagline"),
            movie_data.get("title"),
            movie_data.get("vote_count"),
            movie_data.get("vote_average"),
            movie_data.get("backdrop_path"),
            movie_data.get("poster_path"),

            db.jdump(movie_data.get("genres")),
            db.jdump(movie_data.get("production_companies")),
            db.jdump(movie_data.get("production_countries")),
            db.jdump(movie_data.get("spoken_languages")),
        ))

    if movie_rows:
        movies_repo.insert_movies(movie_rows)
        logger.info(f"Inserted {len(movie_rows)} new movies.")

    # ---------------------------------------------------------
    # 4️⃣ FIND MISSING PERSONS
    # ---------------------------------------------------------
    all_person_ids = set(movies_repo.extract_person_ids())

    existing_persons = db.fetchall(f"SELECT tmdb_id FROM {people_table_name}")
    existing_person_ids = {row[0] for row in existing_persons}

    persons_to_fetch = sorted(all_person_ids - existing_person_ids)

    logger.info(f"{len(persons_to_fetch)} new persons to fetch.")

    # ---------------------------------------------------------
    # 5️⃣ FETCH & INSERT NEW PERSONS
    # ---------------------------------------------------------
    person_rows = []

    for person_id in tqdm(persons_to_fetch, disable=not SHOW_PROGRESS_BAR):
        person_data = letterboxd_client.fetch_person_data(person_id)

        person_rows.append((
            person_data.get("tmdb_id"),
            person_data.get("imdb_id"),
            person_data.get("name"),
            person_data.get("biography"),
            person_data.get("birthday"),
            person_data.get("deathday"),
            person_data.get("place_of_birth"),
            person_data.get("profile_path"),
            person_data.get("popularity"),
            person_data.get("gender"),
            person_data.get("known_for_department"),
            person_data.get("homepage"),
        ))

    if person_rows:
        people_repo.insert_people(person_rows)
        logger.info(f"Inserted {len(person_rows)} new persons.")

    logger.info("✅ update_sources complete.")


if __name__ == "__main__":
    main()


# python -m etl.scripts.update_sources
