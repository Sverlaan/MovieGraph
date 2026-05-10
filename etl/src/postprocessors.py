import logging
import numpy as np
import pandas as pd
from etl.src.dataclass import EdgeDataset, NodeDataset

logger = logging.getLogger(__name__)


def set_recommendations(neo4j_io, recommender, usernames, ratings_df, blacklists_df):
    """
    Get recommendations from the recommender and write them as PREDICTED edges in Neo4j.
    """
    recommend_df = recommender.get_recommendations_users(
        usernames=usernames,
        ratings_df=ratings_df,
        blacklists_df=blacklists_df
    )

    recommend_edges = EdgeDataset(
        type="PREDICTED",
        source_label="User",
        target_label="Movie",
        source_key="username",
        target_key="slug",
        dataframe=recommend_df
    )
    neo4j_io.write_edges(recommend_edges)


def set_mf_similarity_index(neo4j_io, recommender):
    """
    Fetch MF embeddings from the recommender, write them to Movie nodes, and create a vector index for similarity search.
    """

    # Get embeddings
    logger.info("📥 Fetching MF embeddings from recommender")
    df = recommender.get_embeddings()
    df["mf_embedding"] = df["mf_features"].apply(
        lambda x: np.asarray(x, dtype=float).tolist()
    )
    embeddings_df = df[["slug", "mf_embedding"]]
    logger.info("✍️ Writing embeddings to Movie nodes")

    # Write embeddings to Movie nodes
    query = f"""
    UNWIND $rows AS row
    MATCH (m:Movie {{slug: row.slug}})
    SET m.mf_embedding = row.mf_embedding
    """
    neo4j_io.run_dataframe_in_batches(
        embeddings_df,
        query,
    )
    logger.info("✅ MF embeddings written to graph")

    # Create vector index
    embedding_dim = len(embeddings_df.iloc[0]["mf_embedding"])
    logger.info(
        "📐 Creating vector index '%s' (dim=%d, similarity=%s)",
        "movie_mf_embedding_index",
        embedding_dim,
        "cosine",
    )
    query = f"""
        CREATE VECTOR INDEX movie_mf_embedding_index IF NOT EXISTS
        FOR (m:Movie)
        ON (m.mf_embedding)
        OPTIONS {{
            indexConfig: {{
                `vector.dimensions`: {embedding_dim},
                `vector.similarity_function`: 'cosine'
            }}
        }}
        """
    neo4j_io.run_query(query)
    logger.info("✅ Vector index ready")


def set_trending(neo4j_io, letterboxd_client):
    """
    Fetch trending movies from Letterboxd and write their popularity rank to Movie nodes in Neo4j.
    """

    popularity_df = letterboxd_client.get_trending_movies(from_csv=True)
    logger.info("✍️ Writing popularity scores to Movie nodes")

    query = f"""
        UNWIND $rows AS row
        MATCH (m:Movie {{slug: row.slug}})
        SET m.popularity_rank = row.rank
        """

    neo4j_io.run_dataframe_in_batches(
        popularity_df,
        query,
    )
    logger.info("✅ Popularity scores written to graph")
