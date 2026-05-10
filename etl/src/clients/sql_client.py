import json
import sqlite3
from typing import Any, Iterable, List


class SQLiteClient:
    def __init__(self, db_path: str):
        self.db_path = db_path

    # -------------------------
    # Connection
    # -------------------------
    def _connect(self):
        return sqlite3.connect(self.db_path)

    # -------------------------
    # Execution helpers
    # -------------------------
    def execute(self, query: str, params: tuple | None = None):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            conn.commit()

    def executemany(self, query: str, rows: Iterable[tuple]):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.executemany(query, rows)
            conn.commit()

    def fetchall(self, query: str, params: tuple | None = None):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            return cursor.fetchall()

    # -------------------------
    # JSON helper
    # -------------------------
    @staticmethod
    def jdump(value: Any):
        return json.dumps(value) if value is not None else None


class MoviesRepository:
    def __init__(self, db_client: SQLiteClient, table_name: str):
        self.db = db_client
        self.table_name = table_name

    # ---------------------------------------
    # Table Creation
    # ---------------------------------------
    def create_table(self):
        query = f"""
        CREATE TABLE IF NOT EXISTS {self.table_name} (
            slug TEXT PRIMARY KEY,
            lb_title TEXT,
            lb_year INTEGER,
            lb_rating REAL,
            lb_watchers INTEGER,
            lb_runtime INTEGER,
            lb_plot TEXT,
            lb_tagline TEXT,
            lb_trailer TEXT,
            lb_poster TEXT,
            lb_banner TEXT,

            lb_studios TEXT,
            lb_countries TEXT,
            lb_languages TEXT,
            lb_actor_slugs TEXT,
            lb_director_slugs TEXT,
            lb_genres TEXT,
            lb_themes TEXT,
            lb_mini_themes TEXT,

            lb_tmdb_id INTEGER,
            lb_imdb_id TEXT,
            lb_letterboxd_id INTEGER,

            lb_tmdb_url TEXT,
            lb_imdb_url TEXT,
            lb_letterboxd_url TEXT,

            belongs_to_collection TEXT,
            budget INTEGER,
            status TEXT,
            homepage TEXT,
            overview TEXT,
            original_language TEXT,
            original_title TEXT,
            popularity REAL,
            release_date TEXT,
            revenue INTEGER,

            cast TEXT,
            crew TEXT,
            keywords TEXT,

            runtime INTEGER,
            tmdb_id INTEGER,
            imdb_id TEXT,
            tagline TEXT,
            title TEXT,
            vote_count INTEGER,
            vote_average REAL,
            backdrop_path TEXT,
            poster_path TEXT,

            genres TEXT,
            production_companies TEXT,
            production_countries TEXT,
            spoken_languages TEXT
        )
        """
        self.db.execute(query)

    # ---------------------------------------
    # Insert
    # ---------------------------------------
    def insert_movies(self, rows: list[tuple]):
        placeholders = ",".join(["?"] * len(rows[0]))

        query = f"""
        INSERT OR REPLACE INTO {self.table_name}
        VALUES ({placeholders})
        """

        self.db.executemany(query, rows)

    # ---------------------------------------
    # Extract Person IDs
    # ---------------------------------------

    def extract_person_ids(self) -> List[str]:
        rows = self.db.fetchall(
            f"""
            SELECT "cast", "crew"
            FROM {self.table_name}
            WHERE "cast" IS NOT NULL OR "crew" IS NOT NULL
            """
        )

        person_ids = set()

        for cast_json, crew_json in rows:

            if cast_json:
                try:
                    cast = json.loads(cast_json)
                    for person in cast:
                        if person.get("id"):
                            person_ids.add(person["id"])
                except json.JSONDecodeError:
                    pass

            if crew_json:
                try:
                    crew = json.loads(crew_json)
                    for person in crew:
                        if person.get("id"):
                            person_ids.add(person["id"])
                except json.JSONDecodeError:
                    pass

        return sorted(person_ids)


class PeopleRepository:
    def __init__(self, db_client: SQLiteClient, table_name: str):
        self.db = db_client
        self.table_name = table_name

    # ---------------------------------------
    # Table Creation
    # ---------------------------------------
    def create_table(self):
        query = f"""
        CREATE TABLE IF NOT EXISTS {self.table_name} (
            tmdb_id INTEGER PRIMARY KEY,
            imdb_id TEXT,
            name TEXT,
            biography TEXT,
            birthday TEXT,
            deathday TEXT,
            place_of_birth TEXT,
            profile_path TEXT,
            popularity REAL,
            gender INTEGER,
            known_for_department TEXT,
            homepage TEXT
        )
        """
        self.db.execute(query)

    # ---------------------------------------
    # Insert
    # ---------------------------------------
    def insert_people(self, rows: list[tuple]):
        placeholders = ",".join(["?"] * len(rows[0]))

        query = f"""
        INSERT OR REPLACE INTO {self.table_name}
        VALUES ({placeholders})
        """

        self.db.executemany(query, rows)
