from etl.src.clients.sql_client import SQLiteClient, PeopleRepository, MoviesRepository
from etl.src.clients.letterboxd_client import LetterboxdClient
import logging
import os
from dotenv import load_dotenv
import yaml
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

# ---- CREDENTIALS ----
ENV_FILE = "credentials.env"
if os.path.exists(ENV_FILE):
    load_dotenv(ENV_FILE, override=True)

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    TMDB_API_KEY = os.getenv("TMDB_API_KEY")
else:
    raise FileNotFoundError(
        f"Environment file {ENV_FILE} not found. Please create it with the required variables."
    )

# ---- SCRAPER CONFIG ----
DUMMY = True
SHOW_PROGRESS_BAR = True

if DUMMY:
    # Example TMDb person IDs
    logger.info("Running in DUMMY mode: only a small set of persons will be scraped.")
    MOVIES_SOURCE = "etl/dummy_data/sources/movies.db"
else:
    MOVIES_SOURCE = "etl/data/sources/movies.db"


db = SQLiteClient(MOVIES_SOURCE)
movies_repo = MoviesRepository(db, "movies_v5")
people_repo = PeopleRepository(db, "people_v5")
people_repo.create_table()

persons_to_scrape = movies_repo.extract_person_ids()
logger.info(f"Found {len(persons_to_scrape)} unique persons to scrape from movies table.")
# start_index = 0
# end_index = -1
# persons_to_scrape = sorted(persons_to_scrape)[start_index:end_index]
# logger.info(f"Scraping persons from index {start_index} to {end_index} (total {len(persons_to_scrape)} persons).")


client = LetterboxdClient(tmdb_api_key=TMDB_API_KEY)

rows = []

for person_id in tqdm(persons_to_scrape):
    person_data = client.fetch_person_data(person_id)

    rows.append((
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

people_repo.insert_people(rows)

# # python -m etl.scripts.scrapers.scrape_persons
