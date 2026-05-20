from neo4j import GraphDatabase
from neo4j.graph import Node, Relationship, Path
from openai import OpenAI
from app.prompts import cypher_prompt, answer_prompt

from dotenv import load_dotenv
import re
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


def _extract_graph_elements(value, nodes: dict, rels: dict):
    """Recursively pull Node and Relationship objects out of a record value."""
    if isinstance(value, Node):
        eid = value.element_id
        if eid not in nodes:
            props = {k: v for k, v in value.items()
                     if isinstance(v, (str, int, float, bool, type(None)))}
            nodes[eid] = {"id": eid, "labels": list(value.labels), "properties": props}
    elif isinstance(value, Relationship):
        start = value.start_node
        end = value.end_node
        if start is None or end is None:
            return
        eid = value.element_id
        if eid not in rels:
            props = {k: v for k, v in value.items()
                     if isinstance(v, (str, int, float, bool, type(None)))}
            rels[eid] = {
                "id": eid,
                "type": value.type,
                "source": start.element_id,
                "target": end.element_id,
                "properties": props,
            }
            _extract_graph_elements(start, nodes, rels)
            _extract_graph_elements(end, nodes, rels)
    elif isinstance(value, Path):
        for node in value.nodes:
            _extract_graph_elements(node, nodes, rels)
        for rel in value.relationships:
            _extract_graph_elements(rel, nodes, rels)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _extract_graph_elements(item, nodes, rels)
    elif isinstance(value, dict):
        for item in value.values():
            _extract_graph_elements(item, nodes, rels)


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


# ---------------------------
# GRAPH BUILDER
# ---------------------------

def _graph_query(cypher: str, params: dict, nodes: dict, rels: dict):
    """Run a Cypher query that returns nodes/relationships and extract them."""
    with driver.session(database=NEO4J_DATABASE) as session:
        for record in session.run(cypher, **params):  # type: ignore[arg-type]
            for value in record.values():
                _extract_graph_elements(value, nodes, rels)


def _fill_edges_between_nodes(node_ids: list, nodes: dict, rels: dict):
    """Fetch all direct edges between a known set of node element-IDs."""
    if len(node_ids) < 2:
        return
    _graph_query(
        "MATCH (a)-[r]->(b) "
        "WHERE elementId(a) IN $ids AND elementId(b) IN $ids "
        "RETURN a, r, b LIMIT 500",
        {"ids": node_ids}, nodes, rels,
    )


def _fill_bridge_nodes(node_ids: list, nodes: dict, rels: dict, mid_labels: set):
    """Find intermediate nodes on 2-hop paths between any two already-fetched nodes,
    restricted to labels that actually appear in the Cypher query.
    """
    if len(node_ids) < 2 or not mid_labels:
        return
    # Build a label-restricted WHERE clause so Neo4j uses label indexes
    label_filter = " AND (" + " OR ".join(f"mid:{lbl}" for lbl in mid_labels) + ")"
    # Use WITH DISTINCT to collapse duplicate mid nodes before returning,
    # keeping the result set small even with many endpoint pairs
    _graph_query(
        "MATCH (a)-[r1]-(mid)-[r2]-(b) "
        "WHERE elementId(a) IN $ids AND elementId(b) IN $ids "
        "AND elementId(a) <> elementId(b) "
        f"AND NOT elementId(mid) IN $ids{label_filter} "
        "WITH DISTINCT mid, a, r1, b, r2 "
        "RETURN a, r1, mid, r2, b LIMIT 300",
        {"ids": node_ids}, nodes, rels,
    )


def _extract_cypher_node_filters(cypher: str) -> list:
    """Extract (Label, prop, value) triples from a Cypher query.

    Handles both inline patterns and WHERE clause conditions:
      (g:Genre {name: "Romance"})          → ("Genre", "name", "Romance")
      WHERE g.name = "Science Fiction"     → ("Genre", "name", "Science Fiction")
      (u:User {username: "flrz"})          → ("User", "username", "flrz")

    Returns a deduplicated list of (label, prop, value) tuples.
    """
    seen: set = set()
    out: list = []

    def _add(label: str, prop: str, val: str):
        key = (label, prop, val)
        if key not in seen:
            seen.add(key)
            out.append(key)

    # 1. Inline: (var:Label {prop: "value"})
    for label, prop, val in re.findall(
        r'\(\w*:(\w+)\s*\{\s*(\w+)\s*:\s*["\']([^"\']+)["\']',
        cypher,
    ):
        _add(label, prop, val)

    # 2. WHERE clause: build var→Label map from MATCH patterns, then resolve
    #    patterns like  var.prop = "value"  or  var.prop = 'value'
    var_to_label: dict = {}
    for var, label in re.findall(r'\((\w+):(\w+)', cypher):
        var_to_label[var] = label

    for var, prop, val in re.findall(
        r'\b(\w+)\.(\w+)\s*=\s*["\']([^"\']+)["\']',
        cypher,
    ):
        label = var_to_label.get(var)
        if label:
            _add(label, prop, val)

    # toLower(var.prop) = toLower("value")
    for var, prop, val in re.findall(
        r'toLower\((\w+)\.(\w+)\)\s*=\s*toLower\(["\']([^"\']+)["\']\)',
        cypher,
    ):
        label = var_to_label.get(var)
        if label:
            _add(label, prop, val)

    return out


def _graph_fallback_movie_detail(slug: str, nodes: dict, rels: dict):
    _graph_query(
        "MATCH (m:Movie {slug: $slug})-[r]->(n) "
        "WHERE NOT n:Keyword AND NOT n:MiniTheme RETURN m, r, n LIMIT 60",
        {"slug": slug}, nodes, rels)
    _graph_query(
        "MATCH (p:Person)-[r:ACTED_IN]->(m:Movie {slug: $slug}) "
        "RETURN p, r, m ORDER BY r.billing_order ASC LIMIT 8",
        {"slug": slug}, nodes, rels)
    _graph_query(
        "MATCH (p:Person)-[r:WORKED_ON]->(m:Movie {slug: $slug}) "
        "WHERE r.job = 'Director' RETURN p, r, m",
        {"slug": slug}, nodes, rels)


def build_graph(cypher: str, results: list, result_type: str) -> dict:  # noqa: C901
    """Build a graph that shows exactly the nodes/edges matching the query results.

    Strategy:
    1. For movie_detail, use targeted queries (connected nodes not in flat results).
    2. For all other types, collect entity identifiers from the flat results AND
       from any inline {key: 'value'} literals in the Cypher itself (to capture
       entities like users that don't appear as their own result rows).
       Fetch those exact nodes, then fill only the edges that exist between them.
    """
    nodes: dict = {}
    rels: dict = {}

    # Shortest-path queries return Path objects; re-run and extract directly
    if re.search(r'\bshortestPath\b|\ballShortestPaths\b', cypher, re.IGNORECASE):
        _graph_query(cypher, {}, nodes, rels)
        return {"nodes": list(nodes.values()), "edges": list(rels.values())}

    if result_type == "movie_detail":
        slug = results[0].get("slug") if results else None
        if slug:
            _graph_fallback_movie_detail(slug, nodes, rels)
        return {"nodes": list(nodes.values()), "edges": list(rels.values())}

    # --- Collect entity IDs from results ---
    slugs = list(dict.fromkeys(r["slug"] for r in results if r.get("slug")))
    person_names = list(dict.fromkeys(r["name"] for r in results if r.get("name")))
    usernames = list(dict.fromkeys(r["username"] for r in results if r.get("username")))

    # Pull inline node filter literals from the Cypher itself, grouped by label+prop
    node_filters: dict = {}  # (Label, prop) → [values]
    for label, prop, val in _extract_cypher_node_filters(cypher):
        node_filters.setdefault((label, prop), []).append(val)

    # Merge inline Cypher literals into result-derived lists
    for val in node_filters.get(("Movie", "slug"), []):
        if val not in slugs:
            slugs.append(val)
    for val in node_filters.get(("Person", "name"), []):
        if val not in person_names:
            person_names.append(val)
    for val in node_filters.get(("User", "username"), []):
        if val not in usernames:
            usernames.append(val)

    # Fetch the exact nodes
    if slugs:
        _graph_query("MATCH (m:Movie) WHERE m.slug IN $slugs RETURN m",
                     {"slugs": slugs[:50]}, nodes, rels)
    if person_names:
        _graph_query("MATCH (p:Person) WHERE p.name IN $names RETURN p",
                     {"names": person_names[:50]}, nodes, rels)
    if usernames:
        _graph_query("MATCH (u:User) WHERE u.username IN $usernames RETURN u",
                     {"usernames": usernames[:20]}, nodes, rels)

    # Track which labels are already covered to avoid over-fetching via WHERE clauses
    # (e.g. WHERE m.status = "Released" must not pull all released movies).
    result_labels = set()
    if slugs:
        result_labels.add("Movie")
    if person_names:
        result_labels.add("Person")
    if usernames:
        result_labels.add("User")

    # Properties that uniquely identify a specific node — always fetch these even
    # when the label is already covered by result rows (e.g. title: "Inception").
    # Generic filter props (status, release_year, …) are skipped for result labels
    # to avoid pulling every matching node in the DB.
    identity_props = {"title", "name", "slug", "person_slug", "username"}

    skip_pairs = {("Movie", "slug"), ("Person", "name"), ("User", "username")}
    for (label, prop), values in node_filters.items():
        if (label, prop) in skip_pairs:
            continue
        if label in result_labels and prop not in identity_props:
            continue
        _graph_query(
            f"MATCH (n:{label}) WHERE n.`{prop}` IN $vals RETURN n",
            {"vals": values[:20]}, nodes, rels,
        )

    if not nodes:
        return {"nodes": [], "edges": []}

    # Labels referenced in the Cypher pattern that aren't already fetched as result nodes
    # — these are the only allowed intermediate bridge node types
    cypher_labels = set(re.findall(r'\(\w*:(\w+)', cypher))
    mid_labels = cypher_labels - result_labels

    # Find intermediate nodes on 2-hop paths between any two result nodes,
    # restricted to the labels actually used in the query
    _fill_bridge_nodes(list(nodes.keys()), nodes, rels, mid_labels)

    # Fill all direct edges across the now-expanded node set
    _fill_edges_between_nodes(list(nodes.keys()), nodes, rels)

    return {"nodes": list(nodes.values()), "edges": list(rels.values())}


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

    # Single movie with detail fields
    if len(results) == 1 and "poster" in keys and ("plot" in keys or "banner" in keys):
        return "movie_detail"

    # List of movies
    if "poster" in keys and "title" in keys:
        return "movie_list"

    # List of persons
    if "avatar" in keys or "picture" in keys:
        return "person_list"

    return "text"


def ask_graph(question, max_retries=2):
    schema_text = format_schema(SCHEMA)

    error = None
    cypher = ""
    empty_graph = {"nodes": [], "edges": []}

    for _ in range(max_retries + 1):
        cypher = generate_cypher(question, schema_text, error)

        try:
            results = run_cypher(cypher)
        except Exception as e:
            error = str(e)
            continue

        answer = generate_answer(question, results)
        result_type = detect_result_type(results)
        try:
            graph = build_graph(cypher, results, result_type)
        except Exception:
            graph = empty_graph
        query_tags = _extract_cypher_node_filters(cypher)
        return cypher, results, graph, answer, result_type, query_tags

    return cypher, [], empty_graph, f"Failed to answer: {error}", "text", []


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

        cypher, results, graph, answer, result_type, query_tags = ask_graph(question)

        print("\n🔍 Cypher:")
        print(cypher)

        print("\n💡 Answer:")
        print(answer)
