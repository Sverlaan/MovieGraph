
from etl.src.clients.sql_client import SQLiteClient, MoviesRepository
from etl.src.clients.letterboxd_client import LetterboxdClient
import logging
import os
from dotenv import load_dotenv
import yaml
from tqdm import tqdm
import pandas as pd


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

# --- CREDENTIALS ---
ENV_FILE = 'credentials.env'
if os.path.exists(ENV_FILE):
    load_dotenv(ENV_FILE, override=True)

    # AI
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    TMDB_API_KEY = os.getenv('TMDB_API_KEY')
else:
    raise FileNotFoundError(f"Environment file {ENV_FILE} not found. Please create it with the required variables.")


# ----------------------------------------------------------
SHOW_PROGRESS_BAR = True
DUMMY = True

if DUMMY:
    logger.info("Running in DUMMY mode: only a small set of movies will be scraped.")
    MOVIES_SOURCE = "etl/dummy_data/sources/movies.db"
    slugs_to_scrape = ['inception', 'the-dark-knight', 'the-dark-knight-rises', 'interstellar', 'fight-club', 'the-matrix',
                       'pulp-fiction', 'the-godfather', 'the-shawshank-redemption', 'brokeback-mountain', 'groener-gras', 'dream-land-express']
else:
    MOVIES_SOURCE = "etl/data/sources/movies.db"
    slugs_to_scrape = pd.read_csv("etl/data/sources/movies.csv")["slug"].tolist()  # Scraping all movies that exists in a movies CSV file.
    slugs_to_scrape = sorted(set(slugs_to_scrape))

db = SQLiteClient(MOVIES_SOURCE)
repo = MoviesRepository(db, "movies_v5")
repo.create_table()
client = LetterboxdClient(tmdb_api_key=TMDB_API_KEY)

# start_index = 2000
# end_index = -1
# slugs_to_scrape = sorted(slugs_to_scrape)[start_index:end_index]
# logger.info(f"Scraping movies from index {start_index} to {end_index} (total {len(slugs_to_scrape)} movies).")
# logger.info(f"Scraping {len(slugs_to_scrape)} movies.")

rows = []

for slug in tqdm(slugs_to_scrape):
    movie_data = client.fetch_movie_data(slug)

    rows.append((
        # ---- Letterboxd fields (always present) ----
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

        # ---- TMDb fields (may be missing) ----
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

repo.insert_movies(rows)

# python -m etl.scripts.scrapers.scrape_movies
