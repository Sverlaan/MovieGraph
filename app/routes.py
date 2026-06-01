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
CALL { WITH m
  OPTIONAL MATCH (a:Person)-[act:ACTED_IN]->(m)
  WITH a, act ORDER BY act.billing_order ASC
  RETURN collect(CASE WHEN a IS NOT NULL
    THEN {name: a.name, avatar: a.picture, person_slug: a.person_slug, character: act.character}
    ELSE null END)[0..20] AS cast
}
CALL { WITH m
  OPTIONAL MATCH (d:Person)-[:WORKED_ON {job: 'Director'}]->(m)
  RETURN collect(CASE WHEN d IS NOT NULL
    THEN {name: d.name, avatar: d.picture, person_slug: d.person_slug}
    ELSE null END) AS directors
}
CALL { WITH m
  OPTIONAL MATCH (p:Person)-[w:WORKED_ON]->(m)
  WHERE w.job IS NOT NULL AND w.job <> 'Director'
  WITH p, w ORDER BY w.job ASC
  RETURN collect(CASE WHEN p IS NOT NULL
    THEN {name: p.name, avatar: p.picture, person_slug: p.person_slug, job: w.job}
    ELSE null END)[0..10] AS crew
}
CALL { WITH m
  OPTIONAL MATCH (o:OscarNom)-[:NOMINATED_MOVIE]->(m)
  RETURN collect(CASE WHEN o IS NOT NULL
    THEN {category: o.canonical_category, year: o.year, winner: o.winner}
    ELSE null END) AS oscar_noms
}
CALL { WITH m
  OPTIONAL MATCH (m)-[:BELONGS_TO_COLLECTION]->(c:Collection)
  WITH m, c
  OPTIONAL MATCH (all_col:Movie)-[:BELONGS_TO_COLLECTION]->(c)
  WITH c, all_col ORDER BY all_col.release_year ASC
  RETURN head(collect(DISTINCT c.name)) AS collection_name,
         collect(CASE WHEN all_col IS NOT NULL
           THEN {title: all_col.title, poster: all_col.poster, banner: all_col.banner, slug: all_col.slug, year: all_col.release_year}
           ELSE null END) AS collection_movies
}
RETURN
  m.title AS title, m.release_year AS year, m.rating AS rating, m.runtime AS runtime,
  m.plot AS plot, m.tagline AS tagline, m.poster AS poster, m.banner AS banner,
  m.imdb_url AS imdb_url, m.tmdb_url AS tmdb_url, m.letterboxd_url AS letterboxd_url, m.trailer AS trailer_url, m.slug AS slug,
  directors, cast, crew,
  [(m)-[:PRODUCED_IN]->(co:Country) | co.name] AS countries,
  [(m)-[:SPOKEN_IN]->(l:Language) | l.english_name] AS languages,
  [(m)-[:HAS_GENRE]->(g:Genre) | g.name] AS genres,
  [(m)-[:HAS_MINI_THEME]->(t:MiniTheme) | t.name] AS mini_themes,
  oscar_noms, collection_name, collection_movies
"""

_SIMILAR_MOVIES_CYPHER = """
MATCH (m:Movie {slug: $slug})
WHERE m.mf_embedding IS NOT NULL
CALL db.index.vector.queryNodes('movie_mf_embedding_index', 20, m.mf_embedding)
YIELD node, score
WHERE node.slug <> $slug AND node.rating IS NOT NULL
AND NOT (node)-[:BELONGS_TO_COLLECTION]->(:Collection)<-[:BELONGS_TO_COLLECTION]-(m)  // Exclude movies from the same collection
RETURN node.title AS title, node.release_year AS year, node.poster AS poster,
       node.banner AS banner, node.slug AS slug, node.rating AS rating
LIMIT 6
"""


@router.get("/api/movie/{slug}")
def get_movie_detail(slug: str):
    results = run_cypher_params(_MOVIE_DETAIL_CYPHER, {"slug": slug})
    if not results:
        return {}
    return serialize_value(results[0])


@router.get("/api/movie/{slug}/similar")
def get_similar_movies(slug: str):
    results = run_cypher_params(_SIMILAR_MOVIES_CYPHER, {"slug": slug})
    return serialize_results(results)


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
