import os
import re
import requests
from typing import Any, Dict, List, Optional, Set, Tuple
import json
from pathlib import Path

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
NOTION_VERSION = "2025-09-03"
BASE_URL = "https://api.notion.com/v1"

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json",
}


def get_database_2025(database_id: str) -> Dict[str, Any]:
    """
    2025-09-03: GET /v1/databases/{database_id}
    Returns a database object that includes a list of child data_sources.
    """
    url = f"{BASE_URL}/databases/{database_id}"
    r = requests.get(url, headers=HEADERS, timeout=60)
    if not r.ok:
        raise RuntimeError(f"GET database failed: {r.status_code} {r.text}")
    return r.json()


def get_data_source(data_source_id: str) -> Dict[str, Any]:
    """
    2025-09-03: GET /v1/data_sources/{data_source_id}
    Returns schema/properties for the data source.
    """
    url = f"{BASE_URL}/data_sources/{data_source_id}"
    r = requests.get(url, headers=HEADERS, timeout=60)
    if not r.ok:
        raise RuntimeError(f"GET data source failed: {r.status_code} {r.text}")
    return r.json()


def query_data_source_all(data_source_id: str, page_size: int = 100) -> List[Dict[str, Any]]:
    """
    2025-09-03: POST /v1/data_sources/{data_source_id}/query
    Returns all pages (rows) in that data source (cursor-paginated).
    """
    url = f"{BASE_URL}/data_sources/{data_source_id}/query"
    results: List[Dict[str, Any]] = []
    payload: Dict[str, Any] = {"page_size": page_size}

    while True:
        r = requests.post(url, headers=HEADERS, json=payload, timeout=60)
        if not r.ok:
            raise RuntimeError(f"Query data source failed: {r.status_code} {r.text}")

        data = r.json()
        results.extend(data.get("results", []))
        next_cursor = data.get("next_cursor")
        if not next_cursor:
            break
        payload["start_cursor"] = next_cursor

    return results


def pick_primary_data_source_id(db_obj: Dict[str, Any]) -> str:
    """
    Most normal databases will have exactly one data source.
    We take the first one by default.
    """
    data_sources = db_obj.get("data_sources", [])
    if not data_sources:
        raise RuntimeError("No data_sources found on this database. Is it shared with your integration?")
    return data_sources[0]["id"]


def get_page(page_id: str) -> Dict[str, Any]:
    url = f"{BASE_URL}/pages/{page_id}"
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    return r.json()


# ---------- Property extraction helpers ----------
def plain_text(rich_text_list: List[Dict[str, Any]]) -> str:
    return "".join(x.get("plain_text", "") for x in (rich_text_list or [])).strip()


def get_title_prop(props: Dict[str, Any], prop_name: str = "Name") -> str:
    p = props.get(prop_name)
    if not p:
        return ""
    if p["type"] == "title":
        return plain_text(p["title"])
    return ""


def get_select_or_multiselect(props: Dict[str, Any], prop_name: str) -> List[str]:
    p = props.get(prop_name)
    if not p:
        return []
    if p["type"] == "select" and p["select"]:
        return [p["select"]["name"]]
    if p["type"] == "multi_select":
        return [x["name"] for x in p["multi_select"]]
    return []


def get_relation_ids(props: Dict[str, Any], prop_name: str) -> List[str]:
    p = props.get(prop_name)
    if not p:
        return []
    if p["type"] == "relation":
        return [x["id"] for x in p["relation"]]
    return []


# ---------- ID -> title resolver with cache ----------
class PageTitleResolver:
    def __init__(self, name_prop_guess: str = "Name"):
        self.cache: Dict[str, str] = {}
        self.name_prop_guess = name_prop_guess

    def resolve(self, page_id: str) -> str:
        if page_id in self.cache:
            return self.cache[page_id]

        page = get_page(page_id)
        props = page.get("properties", {})
        # Most of your pages use "Name" as the title property.
        title = get_title_prop(props, self.name_prop_guess)

        # Fallback: find the *first* title property if Name isn't present
        if not title:
            for k, v in props.items():
                if v.get("type") == "title":
                    title = plain_text(v.get("title", []))
                    break

        title = title.strip() or f"(untitled-{page_id[:8]})"
        self.cache[page_id] = title
        return title


def safe_filename(name: str) -> str:
    # Cross-platform safe
    name = name.strip()
    name = re.sub(r'[\\/:"*?<>|]+', "_", name)
    name = re.sub(r"\s+", " ", name)
    return (name[:120] if name else "Untitled") + ".md"


def wikilink(name: str) -> str:
    return f"[[{name}]]"


def write_md_note(out_dir: Path, title: str, frontmatter: Dict[str, Any]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / safe_filename(title)

    # YAML (simple)
    lines = ["---"]
    for k, v in frontmatter.items():
        if v is None or v == [] or v == "":
            continue
        if isinstance(v, list):
            # write as YAML list
            lines.append(f"{k}:")
            for item in v:
                lines.append(f"  - {item}")
        else:
            lines.append(f"{k}: {v}")
    lines.append("---\n")
    lines.append(f"# {title}\n")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def export_terms_to_obsidian(
        container_ds_id: str,
        entity_ds_id: str,
        out_dir: str,
        name_prop: str = "Name",
):
    out_path = Path(out_dir)
    resolver = PageTitleResolver(name_prop_guess=name_prop)

    containers = query_data_source_all(container_ds_id)
    entities = query_data_source_all(entity_ds_id)

    # Export containers
    for row in containers:
        props = row["properties"]
        name = get_title_prop(props, "Name")
        if not name:
            continue

        game = get_select_or_multiselect(props, "Game")
        level = get_select_or_multiselect(props, "Level")
        child_ids = get_relation_ids(props, "Child")
        joins_ids = get_relation_ids(props, "Joins")

        children = [wikilink(resolver.resolve(pid)) for pid in child_ids]
        joins = [wikilink(resolver.resolve(pid)) for pid in joins_ids]

        fm = {
            "type": "container",
            "game": game,
            "level": (level[0] if level else None),
            "children": children,
            "joins": joins,
        }
        write_md_note(out_path, name, fm)

    # Export entities
    for row in entities:
        props = row["properties"]
        name = get_title_prop(props, "Name")
        if not name:
            continue

        game = get_select_or_multiselect(props, "Game")
        parent_ids = get_relation_ids(props, "Parent")
        joins_ids = get_relation_ids(props, "Joins")

        parents = [wikilink(resolver.resolve(pid)) for pid in parent_ids]
        joins = [wikilink(resolver.resolve(pid)) for pid in joins_ids]

        fm = {
            "type": "entity",
            "game": game,
            "parents": parents,
            "joins": joins,
        }
        write_md_note(out_path, name, fm)

    print(f"Export complete. Notes written to: {out_path.resolve()}")
    print(f"Title cache size (resolved pages): {len(resolver.cache)}")


if __name__ == "__main__":
    CONTAINER_DB_ID = "2d9a688e32e280f2971af35b861b5812"
    ENTITY_DB_ID = "2d9a688e32e28035ac63dd88c7320d18"

    # --- Container DB ---
    container_db = get_database_2025(CONTAINER_DB_ID)
    container_ds_id = pick_primary_data_source_id(container_db)
    container_ds = get_data_source(container_ds_id)
    container_rows = query_data_source_all(container_ds_id)

    print("Container data_source_id:", container_ds_id)
    print("Container properties:", list(container_ds.get("properties", {}).keys()))
    print("Container rows:", len(container_rows))

    # --- Entity DB ---
    entity_db = get_database_2025(ENTITY_DB_ID)
    entity_ds_id = pick_primary_data_source_id(entity_db)
    entity_ds = get_data_source(entity_ds_id)
    entity_rows = query_data_source_all(entity_ds_id)

    print("Entity data_source_id:", entity_ds_id)
    print("Entity properties:", list(entity_ds.get("properties", {}).keys()))
    print("Entity rows:", len(entity_rows))
    export_terms_to_obsidian(container_ds_id, entity_ds_id,
                             out_dir="/Users/mathsu/PycharmProjects/HoyoverseGraph/obsidian_terms")
