import asyncio
from fastapi import APIRouter
from pydantic import BaseModel
from app.engine import ask_graph

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


def serialize_graph(graph):
    """Graph nodes/edges already contain only primitive property values; just run
    the generic serializer to handle any date fields that slipped through."""
    return serialize_value(graph)


@router.post("/ask")
async def ask(request: QuestionRequest):
    cypher, results, graph, answer, result_type, query_tags = await asyncio.to_thread(
        ask_graph, request.question
    )
    return {
        "answer": answer,
        "result_type": result_type,
        "results": serialize_results(results),
        "graph": serialize_graph(graph),
        "cypher": cypher,
        "query_tags": [{"label": lbl, "value": val} for lbl, _prop, val in query_tags],
    }
