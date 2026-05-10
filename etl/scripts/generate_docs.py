import math
import yaml
from pathlib import Path
from datetime import datetime
from graphviz import Digraph

# ----------------------------
# Paths
# ----------------------------

BASE_DIR = Path(__file__).resolve().parents[1]
ONTOLOGY_PATH = BASE_DIR / "ontology" / "ontology.yaml"
DOCS_DIR = BASE_DIR / "ontology" / "docs"
OUTPUT_FILE = DOCS_DIR / "ontology.md"

# ----------------------------
# Utility functions
# ----------------------------


def load_ontology():
    with open(ONTOLOGY_PATH, "r") as f:
        return yaml.safe_load(f)


def ensure_docs_dir():
    DOCS_DIR.mkdir(parents=True, exist_ok=True)


def sort_dict(d):
    return dict(sorted(d.items(), key=lambda x: x[0]))


def stats_summary(nodes, edges):
    total_node_props = sum(len(n.get("properties", {})) for n in nodes.values())
    total_edge_props = sum(len(e.get("properties", {})) for e in edges.values())

    return f"""
## 📊 Ontology Summary

| Metric | Value |
|--------|-------|
| Node Types | {len(nodes)} |
| Relationship Types | {len(edges)} |
| Total Node Properties | {total_node_props} |
| Total Relationship Properties | {total_edge_props} |
| Generated At | {datetime.utcnow().isoformat()} UTC |
"""

# ============================================================
# Colors (Light Blue)
# ============================================================


NODE_FILL_COLOR = "#E8F4FD"  # light blue
NODE_BORDER_COLOR = "#2c3e50"  # dark blue
EDGE_COLOR = "#555555"

# ============================================================
# GRAPHVIZ — STRUCTURAL (SVG)
# ============================================================


def generate_graphviz_structural(nodes, edges):
    output_path = DOCS_DIR / "schema"

    dot = Digraph("OntologyStructural", format="svg")
    dot.attr(rankdir="LR", bgcolor="white")
    dot.attr(
        "node",
        shape="box",
        style="rounded,filled",
        fontsize="12",
        fillcolor=NODE_FILL_COLOR,
        color=NODE_BORDER_COLOR,
        fontname="Helvetica"
    )

    for node_name in nodes.keys():
        dot.node(node_name)

    for edge_name, config in edges.items():
        dot.edge(
            config["source"],
            config["target"],
            label=edge_name,
            arrowhead="vee",
            color=EDGE_COLOR,
            fontname="Helvetica",
            fontsize="10"
        )

    dot.render(str(output_path), cleanup=True)
    return "schema.svg"

# ============================================================
# GRAPHVIZ — DETAILED (SVG)
# ============================================================


def generate_graphviz_detailed(nodes, edges):
    output_path = DOCS_DIR / "schema_detailed"

    dot = Digraph("OntologyDetailed", format="svg")
    dot.attr(rankdir="LR", bgcolor="white", fontname="Helvetica")

    dot.attr(
        "node",
        shape="box",
        style="rounded,filled",
        fillcolor=NODE_FILL_COLOR,
        color=NODE_BORDER_COLOR,
        fontname="Helvetica",
        fontsize="11"
    )

    dot.attr("edge", fontname="Helvetica", fontsize="10", color=EDGE_COLOR)

    for node_name, config in nodes.items():
        props = config.get("properties", {})
        keys = config.get("keys", [])

        label_parts = [f"<B>{node_name}</B>"]

        if props:
            label_parts.append("<BR/><FONT POINT-SIZE='9'>")
            for prop_name, prop_info in props.items():
                dtype = prop_info.get("type", "unknown") if isinstance(prop_info, dict) else prop_info
                key_marker = " 🔑" if prop_name in keys else ""
                label_parts.append(f"{prop_name}: {dtype}{key_marker}<BR/>")
            label_parts.append("</FONT>")

        html_label = "<" + "".join(label_parts) + ">"
        dot.node(node_name, label=html_label)

    for edge_name, config in edges.items():
        dot.edge(
            config["source"],
            config["target"],
            label=edge_name,
            arrowhead="vee"
        )

    dot.render(str(output_path), cleanup=True)
    return "schema_detailed.svg"

# ============================================================
# PROPERTY TABLE
# ============================================================


def property_table(properties, keys=None):
    if not properties:
        return "_No properties_\n"

    keys = keys or []
    lines = [
        "| Property | Type | Description |",
        "|----------|------|-------------|"
    ]

    for name, prop_info in properties.items():
        if isinstance(prop_info, dict):
            dtype = prop_info.get("type", "unknown")
            desc = prop_info.get("description", "")
        else:
            dtype = prop_info
            desc = ""

        if name in keys:
            lines.append(f"| **`{name}`** 🔑 | `{dtype}` | {desc} |")
        else:
            lines.append(f"| `{name}` | `{dtype}` | {desc} |")

    return "\n".join(lines) + "\n"

# ============================================================
# MAIN DOCUMENT GENERATOR
# ============================================================


def generate(nodes, edges):
    content = "# MovieGraph Ontology\n"
    content += stats_summary(nodes, edges)

    # Structural diagram
    content += "\n## Schema\n\n"
    structural_svg = generate_graphviz_structural(nodes, edges)
    content += f"![Structural Schema]({structural_svg})\n\n"

    # Detailed diagram
    content += "## Schema (Detailed)\n\n"
    detailed_svg = generate_graphviz_detailed(nodes, edges)
    content += f"![Detailed Schema]({detailed_svg})\n\n"

    # Node definitions
    content += "## Nodes\n"
    for node_name, config in nodes.items():
        keys = config.get("keys", [])
        description = config.get("description", "")
        content += f"\n### {node_name}\n\n"
        content += f"**Description:** {description}\n\n"
        content += f"**Primary Keys:** {', '.join(f'`{k}`' for k in keys) if keys else '_None_'}\n\n"
        content += property_table(config.get("properties", {}), keys)

    # Edge definitions
    content += "\n## Relationships\n"
    for edge_name, config in edges.items():
        content += f"\n### {edge_name}\n\n"
        content += f"**Description:** {config.get('description', '')}\n\n"
        content += f"- **Source:** `{config['source']}` (*{config['source_key']}*)\n"
        content += f"- **Target:** `{config['target']}` (*{config['target_key']}*)\n\n"
        content += property_table(config.get("properties", {}))

    return content

# ============================================================
# MAIN
# ============================================================


def main():
    ensure_docs_dir()
    ontology = load_ontology()

    nodes = sort_dict(ontology.get("nodes", {}))
    edges = sort_dict(ontology.get("edges", {}))

    markdown = generate(nodes, edges)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(markdown)

    print(f"Ontology documentation generated at {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

# python -m etl.scripts.generate_docs
