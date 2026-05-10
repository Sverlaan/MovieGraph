from etl.scripts.update_sources import main as update_sources
from etl.scripts.build_graph import main as build_graph


def main():
    update_sources()
    build_graph()
