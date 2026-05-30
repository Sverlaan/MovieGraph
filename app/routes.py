import asyncio
from fastapi import APIRouter
from pydantic import BaseModel
from app.engine import ask_graph, run_cypher_params

router = APIRouter()


class QuestionRequest(BaseModel):
    question: str


def serialize_value(v):
    """Convert Neo4j / Python types to JSON-serializable forms."""
    if hasattr(v, "isoformat"):  # date / datetime
        return v.isoformat()
    if isinstance(v, dict):
        return {k: serialize_value(val) for k, val in v.items()}
    if isinstance(v, list):
        return [serialize_value(item) for item in v]
    return v


def serialize_results(results):
    return [{k: serialize_value(v) for k, v in record.items()} for record in results]



_MOVIE_DETAIL_CYPHER = """
MATCH (m:Movie {slug: $slug})
OPTIONAL MATCH (d:Person)-[:WORKED_ON {job: 'Director'}]->(m)
WITH m, collect(DISTINCT d.name) AS directors
OPTIONAL MATCH (a:Person)-[act:ACTED_IN]->(m)
WITH m, directors, a, act ORDER BY act.billing_order ASC
WITH m, directors, collect(a.name)[0..5] AS cast
OPTIONAL MATCH (m)-[:PRODUCED_IN]->(c:Country)
WITH m, directors, cast, collect(DISTINCT c.name) AS countries
OPTIONAL MATCH (m)-[:SPOKEN_IN]->(l:Language)
WITH m, directors, cast, countries, collect(DISTINCT l.english_name) AS languages
OPTIONAL MATCH (m)-[:HAS_GENRE]->(g:Genre)
WITH m, directors, cast, countries, languages, collect(DISTINCT g.name) AS genres
OPTIONAL MATCH (m)-[:HAS_MINI_THEME]->(t:MiniTheme)
WITH m, directors, cast, countries, languages, genres, collect(DISTINCT t.name) AS mini_themes
RETURN
  m.title AS title, m.release_year AS year, m.rating AS rating, m.runtime AS runtime,
  m.plot AS plot, m.tagline AS tagline, m.poster AS poster, m.banner AS banner,
  m.imdb_url AS imdb_url, m.letterboxd_url AS letterboxd_url, m.slug AS slug,
  directors, cast, countries, languages, genres, mini_themes
"""


@router.get("/api/movie/{slug}")
def get_movie_detail(slug: str):
    results = run_cypher_params(_MOVIE_DETAIL_CYPHER, {"slug": slug})
    if not results:
        return {}
    return serialize_value(results[0])


@router.post("/ask")
async def ask(request: QuestionRequest):
    cypher, results, answer, result_type = await asyncio.to_thread(
        ask_graph, request.question
    )
    return {
        "answer": answer,
        "result_type": result_type,
        "results": serialize_results(results),
        "cypher": cypher,
    }
