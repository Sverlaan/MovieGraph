import yaml
from etl.src.transforms import (
    TYPE_CASTERS,
    preprocess_movies,
    explode_json,
    cast_properties_from_ontology,
    preprocess_people,
)
from etl.src.postprocessors import (
    set_recommendations,
    set_mf_similarity_index,
    set_trending,
)
from etl.src.dataclass import NodeDataset, EdgeDataset
from typing import List
import logging
import pandas as pd
import sqlite3

logger = logging.getLogger(__name__)

TRANSFORMS = {
    "preprocess_movies": preprocess_movies,
    "preprocess_people": preprocess_people,
    "explode_json": explode_json,
}


def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)


class OntologyETL:

    def __init__(self, neo4j_io, recommender, usernames, ontology_dir, sources_dir, csv_dir="data/exports"):
        self.neo4j_io = neo4j_io
        self.recommender = recommender
        self.node_datasets: List[NodeDataset] = []
        self.edge_datasets: List[EdgeDataset] = []
        self.dataframes = {}
        self.csv_dir = csv_dir
        self.usernames = usernames

        ontology = load_yaml(f"{ontology_dir}/ontology.yaml")
        self.nodes_ontology = ontology["nodes"]
        self.edges_ontology = ontology["edges"]

        self.mappings = load_yaml(f"{ontology_dir}/mappings.yaml")["mappings"]
        self.sources = load_yaml(f"{sources_dir}")["sources"]

    # --------------------------------------------------
    # 🔹 NEW: Normalize property definitions
    # --------------------------------------------------
    def _extract_property_types(self, properties: dict) -> dict:
        """
        Convert ontology property definitions into a flat {prop: type} dict.
        Supports both:
        - old format: {prop: "string"}
        - new format: {prop: {type: "string", description: "..."}}
        """
        normalized = {}
        for prop, definition in properties.items():
            if isinstance(definition, dict):
                normalized[prop] = definition.get("type")
            else:
                normalized[prop] = definition
        return normalized

    # --------------------------------------------------

    def run(self, save_to_csv=False):
        self.neo4j_io.recreate_database()
        self.extract()
        self.transform()
        if save_to_csv:
            self._save_to_csv(self.csv_dir)
        self.load()
        self.postprocess()

    def extract(self):
        logger.info("🔍 EXTRACT: get data from sources")
        for name, src in self.sources.items():
            self.dataframes[name] = self._extract_from_source(
                src["path"], src.get("table")
            )

    def transform(self):
        logger.info("🔄 TRANSFORM: mapping data to ontology")

        for mapping in self.mappings:
            df = self.dataframes[mapping["source"]].copy()

            # Apply transformations
            for t in mapping.get("transformations", []):
                if isinstance(t, str):
                    df = TRANSFORMS[t](df)
                elif isinstance(t, dict):
                    name, args = next(iter(t.items()))
                    df = TRANSFORMS[name](df, **args)

            # Rename/select columns
            colmap = mapping["columns"]
            df = df.rename(columns={v: k for k, v in colmap.items()})
            df = df[list(colmap.keys())]

            # ---------------------------
            # 🔹 NODE HANDLING
            # ---------------------------
            if "node" in mapping:
                node = mapping["node"]
                node_config = self.nodes_ontology[node]

                keys = node_config["keys"]
                raw_props = node_config.get("properties", {})
                props = self._extract_property_types(raw_props)

                # Drop rows with NaN in key columns
                df.dropna(subset=keys, inplace=True)

                # Drop duplicates
                df.drop_duplicates(subset=keys, inplace=True)

                if "slug" in keys:
                    temp_keys = list(set(keys) - {"slug"})
                    if temp_keys:
                        df.drop_duplicates(subset=temp_keys, inplace=True)

                # Cast properties using normalized types
                df = cast_properties_from_ontology(
                    df=df,
                    label=node,
                    ontology_props=props,
                )

                self.node_datasets.append(
                    NodeDataset(label=node, keys=keys, dataframe=df)
                )

            # ---------------------------
            # 🔹 EDGE HANDLING
            # ---------------------------
            if "edge" in mapping:
                edge = mapping["edge"]
                edge_config = self.edges_ontology[edge]

                # Drop rows with NaN in source/target keys
                df.dropna(
                    subset=[edge_config["source_key"], edge_config["target_key"]],
                    inplace=True,
                )

                # Keep distinct edge variants (e.g. same person/movie with different jobs).
                # Only collapse fully identical edge rows.
                df.drop_duplicates(inplace=True)

                # Normalize edge properties if present
                raw_edge_props = edge_config.get("properties", {})
                edge_props = self._extract_property_types(raw_edge_props)

                df = cast_properties_from_ontology(
                    df=df,
                    label=edge,
                    ontology_props=edge_props,
                )

                self.edge_datasets.append(
                    EdgeDataset(
                        type=edge,
                        source_label=edge_config["source"],
                        target_label=edge_config["target"],
                        source_key=edge_config["source_key"],
                        target_key=edge_config["target_key"],
                        merge_key=edge_config.get("merge_key"),
                        dataframe=df,
                    )
                )

    def load(self):
        logger.info("🚀 LOAD: writing nodes and edges to Neo4j")

        for node_ds in self.node_datasets:
            self.neo4j_io.write_nodes(node_ds)

        for edge_ds in self.edge_datasets:
            self.neo4j_io.write_edges(edge_ds)

        logger.info("✅ LOAD complete")

    def postprocess(self):
        logger.info("🔧 POST-PROCESS")

        set_recommendations(
            self.neo4j_io,
            self.recommender,
            self.usernames,
            self.dataframes["ratings"],
            self.dataframes["blacklists"],
        )

        set_mf_similarity_index(self.neo4j_io, self.recommender)
        self.neo4j_io.close()

        logger.info("✅ POST-PROCESS complete")

    def _extract_from_source(self, source_path, table_name=None, separator=","):
        if source_path.endswith(".db"):
            with sqlite3.connect(source_path) as conn:
                df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
        elif source_path.endswith(".csv"):
            df = pd.read_csv(source_path, encoding="utf-8-sig", sep=separator)
        else:
            raise ValueError("Unsupported source format. Use .db or .csv")
        return df

    def _save_to_csv(self, directory):
        import os

        os.makedirs(directory + "/nodes", exist_ok=True)
        os.makedirs(directory + "/edges", exist_ok=True)

        for node_dataset in self.node_datasets:
            if not node_dataset.dataframe.empty:
                node_dataset.dataframe.to_csv(
                    f"{directory}/nodes/{node_dataset.label}_nodes.csv",
                    index=False,
                )

        for edge_dataset in self.edge_datasets:
            if not edge_dataset.dataframe.empty:
                edge_dataset.dataframe.to_csv(
                    f"{directory}/edges/{edge_dataset.type}_edges.csv",
                    index=False,
                )
