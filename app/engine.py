from neo4j import GraphDatabase
from openai import OpenAI
from app.prompts import cypher_prompt, answer_prompt

from dotenv import load_dotenv
import yaml
import os
import warnings

# ---- SUPPRESS WARNINGS ----
warnings.filterwarnings("ignore")

# ---- CONFIG ----
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

NEO4J_ENV = config["neo4j_env"]
ONTOLOGY_PATH = config.get("ontology_path", "etl/ontology/ontology.yaml")

# --- CREDENTIALS ---
ENV_FILE = "credentials.env"
if os.path.exists(ENV_FILE):
    load_dotenv(ENV_FILE, override=True)

    NEO4J_URI = os.getenv(f"NEO4J_URI_{NEO4J_ENV}")
    NEO4J_USER = os.getenv(f"NEO4J_USERNAME_{NEO4J_ENV}")
    NEO4J_PASSWORD = os.getenv(f"NEO4J_PASSWORD_{NEO4J_ENV}")
    NEO4J_DATABASE = os.getenv(f"NEO4J_DATABASE_{NEO4J_ENV}")

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
else:
    raise FileNotFoundError(f"{ENV_FILE} not found")

# --- INIT ---
driver = GraphDatabase.driver(
    NEO4J_URI or "",
    auth=(NEO4J_USER or "", NEO4J_PASSWORD or ""),
    notifications_min_severity="OFF"  # 🔕 suppress Neo4j warnings
)

client = OpenAI(api_key=OPENAI_API_KEY)


# ---------------------------
# UTILITIES
# ---------------------------
def clean_cypher(text: str) -> str:
    text = text.strip()

    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) > 1:
            text = parts[1]
        text = text.replace("cypher", "", 1)

    return text.strip()


def format_schema(schema: dict) -> str:
    lines = []

    for node_label, node_data in schema["nodes"].items():
        props = sorted((node_data.get("properties") or {}).keys())
        keys = node_data.get("keys") or []
        lines.append(f"Node :{node_label} keys={keys} props={props}")

    for rel_type, rel_data in schema["relationships"].items():
        source = rel_data.get("source", "?")
        target = rel_data.get("target", "?")
        props = sorted((rel_data.get("properties") or {}).keys())
        lines.append(f"Rel :{source}-[:{rel_type}]->:{target} props={props}")

    return "\n".join(lines)


def simplify_results(results):
    simplified = []

    for record in results:
        clean_record = {}

        for key, value in record.items():
            if hasattr(value, "items"):
                props = dict(value)

                for field in ["name", "title", "id"]:
                    if field in props:
                        clean_record[key] = props[field]
                        break
                else:
                    clean_record[key] = props
            else:
                clean_record[key] = value

        simplified.append(clean_record)

    return simplified


# ---------------------------
# CORE STEPS
# ---------------------------
def get_schema_from_ontology(path=ONTOLOGY_PATH):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Ontology file not found: {path}")

    with open(path, "r") as f:
        ontology = yaml.safe_load(f) or {}

    return {
        "nodes": ontology.get("nodes", {}),
        "relationships": ontology.get("edges", {}),
    }


def generate_cypher(question, schema_text, error=None):
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": cypher_prompt(schema_text, question, error)}],
        temperature=0,
    )

    return clean_cypher(response.choices[0].message.content or "")


def run_cypher(query):
    query = clean_cypher(query)
    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run(query)  # type: ignore[arg-type]
        return [record.data() for record in result]


def run_cypher_params(query: str, params: dict) -> list:
    query = clean_cypher(query)
    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run(query, **params)  # type: ignore[arg-type]
        return [record.data() for record in result]


def generate_answer(question, results):
    if not results:
        return "No results found."

    simplified = simplify_results(results)

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": answer_prompt(question, simplified)}],
        temperature=0.3,
    )

    return (response.choices[0].message.content or "").strip()


SCHEMA = get_schema_from_ontology()


def detect_result_type(results):
    if not results:
        return "text"

    first = results[0]
    keys = set(first.keys())

    if "poster" in keys and "title" in keys:
        return "movie_list"

    if "avatar" in keys or "picture" in keys:
        return "person_list"

    return "text"


def ask_graph(question, max_retries=2):
    schema_text = format_schema(SCHEMA)

    error = None
    cypher = ""

    for _ in range(max_retries + 1):
        cypher = generate_cypher(question, schema_text, error)

        try:
            results = run_cypher(cypher)
        except Exception as e:
            error = str(e)
            continue

        answer = generate_answer(question, results)
        result_type = detect_result_type(results)
        return cypher, results, answer, result_type

    return cypher, [], f"Failed to answer: {error}", "text"


# ---------------------------
# CLI LOOP (CLEAN OUTPUT)
# ---------------------------
if __name__ == "__main__":
    while True:
        question = input("\n❓ ").strip()

        if question.lower() in ["exit", "quit"]:
            break

        if not question:
            continue

        cypher, results, answer, result_type = ask_graph(question)

        print("\n🔍 Cypher:")
        print(cypher)

        print("\n💡 Answer:")
        print(answer)
