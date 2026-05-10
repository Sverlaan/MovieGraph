import logging
import time
from neo4j import GraphDatabase
import pandas as pd

logger = logging.getLogger(__name__)
logging.getLogger("neo4j").setLevel(logging.WARNING)


class Neo4jIO:
    """
    Neo4j Input/Output handler for database operations.
    """

    def __init__(self, uri, user, password, database_name, env=None):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.database_name = database_name
        self.env = env

    def close(self):
        logger.info("🏁 Closing Neo4j driver connection.")
        self.driver.close()

    def recreate_database(self):
        """Drop/recreate the database."""
        logger.info(f"Running Neo4j in environment: {self.env}")
        if self.env == "LOCAL":
            self._drop_database()
            self._create_database()
        elif self.env == "AURA":
            self._delete_graph()
        else:
            raise ValueError(f"Unknown environment: {self.env}")

    def _delete_graph(self):
        """Delete all nodes and relationships in the database."""
        with self.driver.session(database=self.database_name) as session:
            session.run("MATCH (n) DETACH DELETE n")

        logger.info("🗑️ Deleted all nodes and relationships in database '%s'", self.database_name)

    def _drop_database(self):
        """Drop the database if it exists."""
        with self.driver.session(database="system") as sys_session:
            try:
                sys_session.run(f"DROP DATABASE {self.database_name} IF EXISTS")  # type: ignore
                logger.info("🗑️ Dropped database '%s'", self.database_name)
            except Exception as e:
                logger.warning("⚠️ Could not drop database %s: %s", self.database_name, e)

    def _create_database(self):
        """Create the database if it does not exist."""
        with self.driver.session(database="system") as sys_session:
            sys_session.run(f"CREATE DATABASE {self.database_name} IF NOT EXISTS")  # type: ignore
            logger.info("📦 Created database '%s'", self.database_name)

        # Wait until database is online
        with self.driver.session(database="system") as sys_session:
            while True:
                result = sys_session.run(
                    "SHOW DATABASES YIELD name, currentStatus "
                    "WHERE name = $db RETURN currentStatus",
                    db=self.database_name
                ).single()
                if result and result["currentStatus"] == "online":
                    logger.info("🟢 Database '%s' is online.", self.database_name)
                    break
                logger.info("⏳ Waiting for database to come online...")
                time.sleep(1)

    def write_nodes(self, node_dataset):
        start_time = time.time()

        label = node_dataset.label
        keys = node_dataset.keys
        df = node_dataset.dataframe

        for k in keys:
            if k not in df.columns:
                raise ValueError(f"Missing key column '{k}' for node {label}")

        self._set_uniqueness_constraints(label, keys)

        # All columns except the key are node properties
        primary_key = keys[0]
        set_columns = [c for c in df.columns if c != primary_key]
        set_props = ", ".join([f"n.{col} = row.{col}" for col in set_columns])

        query = f"""
            UNWIND $rows AS row
            MERGE (n:{label} {{ {primary_key}: row.{primary_key} }})
            """
        if set_props:
            query += f"\nSET {set_props}"

        self.run_dataframe_in_batches(df, query)
        # logger.info(f"Loaded {len(df)} nodes of label '{label}' in {time.time() - start_time:.2f}s")
        logger.info(
            f"Loaded {len(df):>6} nodes of label {label:<24} in {time.time() - start_time:6.2f}s"
        )

    def write_edges(self, edge_dataset):
        start_time = time.time()

        rel_type = edge_dataset.type
        df = edge_dataset.dataframe

        if df.empty:
            logger.info(f"⚠️ Skipping empty dataset for edge: {rel_type}")
            return

        src_label = edge_dataset.source_label
        tgt_label = edge_dataset.target_label
        src_key = edge_dataset.source_key
        tgt_key = edge_dataset.target_key

        all_columns = list(df.columns)
        merge_key = edge_dataset.merge_key

        if merge_key:
            # MERGE on the dedicated edge key only; SET everything else to allow nulls.
            merge_props = f"{merge_key}: row.{merge_key}"
            set_columns = [c for c in all_columns if c not in [src_key, tgt_key, merge_key]]
            set_clause = "\nSET " + ", ".join([f"r.{p} = row.{p}" for p in set_columns]) if set_columns else ""
            query = f"""
            UNWIND $rows AS row
            MATCH (a:{src_label} {{ {src_key}: row.{src_key} }})
            MATCH (b:{tgt_label} {{ {tgt_key}: row.{tgt_key} }})
            MERGE (a)-[r:{rel_type} {{ {merge_props} }}]->(b){set_clause}
            """
        else:
            # Default: merge on all properties (no nulls allowed in these edges).
            set_columns = [c for c in all_columns if c not in [src_key, tgt_key]]
            merge_props = ", ".join([f"{p}: row.{p}" for p in set_columns])
            query = f"""
            UNWIND $rows AS row
            MATCH (a:{src_label} {{ {src_key}: row.{src_key} }})
            MATCH (b:{tgt_label} {{ {tgt_key}: row.{tgt_key} }})
            MERGE (a)-[r:{rel_type} {{ {merge_props} }}]->(b)
            """

        self.run_dataframe_in_batches(df, query)
        # logger.info(f"Loaded {len(df)} edges of type '{rel_type}' in {time.time() - start_time:.2f}s")
        logger.info(
            f"Loaded {len(df):>6} edges of type  {rel_type:24} in {time.time() - start_time:6.2f}s"
        )

    def _set_uniqueness_constraints(self, label: str, keys: list[str]):
        for key in keys:
            name = f"{label}_{key}_uniq"
            query = f"""
            CREATE CONSTRAINT {name} IF NOT EXISTS
            FOR (n:{label})
            REQUIRE n.{key} IS UNIQUE
            """
            self.run_query(query)

    def run_query(self, query, parameters=None):
        """Execute a Cypher query."""
        with self.driver.session(database=self.database_name) as session:
            result = session.run(query, parameters or {})
            return result.data()

    def _batch_write(self, tx, query, rows):
        """Transaction-level execution of a batch of rows."""
        tx.run(query, {"rows": rows})

    def run_dataframe_in_batches(self, df, query, batch_size=5000):
        """
        Execute a parameterized UNWIND Cypher query with DataFrame batches.
        Each batch is passed as rows=[{...}, ...].
        """
        with self.driver.session(database=self.database_name) as session:
            for i in range(0, len(df), batch_size):
                batch_df = df.iloc[i:i+batch_size]
                # Ensure Neo4j receives real nulls instead of pandas NaN values.
                batch_df = batch_df.astype(object).where(pd.notna(batch_df), None)
                batch_rows = batch_df.to_dict(orient="records")
                session.execute_write(self._batch_write, query, batch_rows)
