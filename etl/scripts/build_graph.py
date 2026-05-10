from etl.src.ontology_etl import OntologyETL
from etl.src.clients.neo4j_io import Neo4jIO  # your existing class
from dotenv import load_dotenv
import yaml
import os
import logging
import sys
from etl.src.clients.letterboxd_client import LetterboxdClient
from etl.src.clients.recommender import Recommender
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

NEO4J_ENV = config["neo4j_env"]
USERNAMES = config["users"]["usernames"]
ONTOLOGY_DIR = config["dirs"]["ontology"]
SOURCES_DIR = config["dirs"]["sources"]
EXPORT_DIR = config["dirs"]["export"]

# LLM = config["models"]['llm']
# EMBEDDINGS_MODEL = config["models"]['embeddings_model']
MF_MODEL_PATH = config["models"]["mf_model_path"]


# --- CREDENTIALS ---
ENV_FILE = 'credentials.env'
if os.path.exists(ENV_FILE):
    load_dotenv(ENV_FILE, override=True)

    # Neo4j
    NEO4J_URI = os.getenv(f'NEO4J_URI_{NEO4J_ENV}')
    NEO4J_USER = os.getenv(f'NEO4J_USERNAME_{NEO4J_ENV}')
    NEO4J_PASSWORD = os.getenv(f'NEO4J_PASSWORD_{NEO4J_ENV}')
    NEO4J_DATABASE = os.getenv(f'NEO4J_DATABASE_{NEO4J_ENV}')

    # AI
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    # TMDB_API_KEY = os.getenv('TMDB_API_KEY')
else:
    raise FileNotFoundError(f"Environment file {ENV_FILE} not found. Please create it with the required variables.")

# ---- DUMMY MODE ----
DUMMY = config.get("dummy_data", False)
if DUMMY:
    logger.warning("⚠️ Running in DUMMY mode with limited data")
    SOURCES_DIR = "etl/ontology/sources_dummy.yaml"
    NEO4J_DATABASE = "dummy"

# ---- Initialize Core Clients ----
letterboxd_client = LetterboxdClient()
neo4j_io = Neo4jIO(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE, NEO4J_ENV)
recommender = Recommender(model_path=MF_MODEL_PATH)


def main():
    OntologyETL(
        neo4j_io=neo4j_io,
        recommender=recommender,
        usernames=USERNAMES,
        ontology_dir=ONTOLOGY_DIR,
        sources_dir=SOURCES_DIR,
        csv_dir=EXPORT_DIR,
    ).run()


if __name__ == "__main__":
    main()


# python -m etl.scripts.build_graph
