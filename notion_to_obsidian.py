"""
Notion (2025-09-03) -> Obsidian Markdown Exporter (Deduped via Joins)

You provide DATABASE IDs (not data_source ids).
The script discovers each database's data_source_id automatically, then queries it.

Outputs:
- One .md note per canonical concept (deduped via Joins)
- YAML frontmatter:
    type: container | entity | container+entity
    game: (multi-select merged list)
    level: (from Container if present)
    parents: [[...]] (from Entity)
    children: [[...]] (from Container)
    aliases: join-derived + small normalized variants (to catch human input errors)

Does NOT export joins as a field (only used during dedupe).

Requirements:
- pip install requests
- export NOTION_TOKEN="secret_..."
- Share the relevant databases with your Notion integration.

Fill in:
    CONTAINER_DB_ID = "..."
    ENTITY_DB_ID    = "..."
    OUT_DIR         = "..."
"""

import os
import re
import requests
from pathlib import Path
from typing import Any, Dict, List, Set, Optional

# ----------------------------- Config -----------------------------
NOTION_TOKEN = os.environ["NOTION_TOKEN"]
NOTION_VERSION = "2025-09-03"
BASE_URL = "https://api.notion.com/v1"

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json",
}


# ------------------------ Notion 2025 API ------------------------
def get_database(database_id: str) -> Dict[str, Any]:
    """
    GET /v1/databases/{database_id}
    In 2025-09-03, this returns database metadata AND its child data_sources.
    """
    url = f"{BASE_URL}/databases/{database_id}"
    r = requests.get(url, headers=HEADERS, timeout=60)
    if not r.ok:
        raise RuntimeError(f"GET database failed: {r.status_code} {r.text}")
    return r.json()


def pick_data_source_id(db_obj: Dict[str, Any]) -> str:
    """
    Most normal Notion databases have exactly one data source in 2025-09-03.
    We pick the first unless you later want more advanced selection.
    """
    data_sources = db_obj.get("data_sources", [])
    if not data_sources:
        raise RuntimeError(
            "No data_sources found for this database. "
            "Most likely: the database is not shared with your integration."
        )
    return data_sources[0]["id"]


def get_data_source(data_source_id: str) -> Dict[str, Any]:
    """
    GET /v1/data_sources/{data_source_id}
    Returns the properties/schema for the data source.
    """
    url = f"{BASE_URL}/data_sources/{data_source_id}"
    r = requests.get(url, headers=HEADERS, timeout=60)
    if not r.ok:
        raise RuntimeError(f"GET data source failed: {r.status_code} {r.text}")
    return r.json()


def query_data_source_all(data_source_id: str, page_size: int = 100) -> List[Dict[str, Any]]:
    """
    POST /v1/data_sources/{data_source_id}/query
    Cursor-paginates to fetch all rows (pages).
    """
    url = f"{BASE_URL}/data_sources/{data_source_id}/query"
    results: List[Dict[str, Any]] = []
    payload: Dict[str, Any] = {"page_size": page_size}

    while True:
        r = requests.post(url, headers=HEADERS, json=payload, timeout=60)
        if not r.ok:
            raise RuntimeError(f"Query failed: {r.status_code} {r.text}")

        data = r.json()
        results.extend(data.get("results", []))

        nxt = data.get("next_cursor")
        if not nxt:
            break
        payload["start_cursor"] = nxt

    return results


def get_page(page_id: str) -> Dict[str, Any]:
    """
    GET /v1/pages/{page_id}
    Used to resolve relation ids -> titles.
    """
    url = f"{BASE_URL}/pages/{page_id}"
    r = requests.get(url, headers=HEADERS, timeout=60)
    if not r.ok:
        raise RuntimeError(f"Get page failed: {r.status_code} {r.text}")
    return r.json()


# ---------------------- Property extraction ----------------------
def plain_text(rich_text_list: List[Dict[str, Any]]) -> str:
    return "".join(x.get("plain_text", "") for x in (rich_text_list or [])).strip()


def get_title_prop(props: Dict[str, Any], prop_name: str = "Name") -> str:
    p = props.get(prop_name)
    if p and p.get("type") == "title":
        return plain_text(p.get("title", []))
    return ""


def get_multi_select(props: Dict[str, Any], prop_name: str) -> List[str]:
    """
    Game is multi-select for you (but we tolerate select just in case).
    """
    p = props.get(prop_name)
    if not p:
        return []
    if p.get("type") == "multi_select":
        return [x["name"] for x in p.get("multi_select", [])]
    if p.get("type") == "select" and p.get("select"):
        return [p["select"]["name"]]
    return []


def get_relation_ids(props: Dict[str, Any], prop_name: str) -> List[str]:
    p = props.get(prop_name)
    if p and p.get("type") == "relation":
        return [x["id"] for x in p.get("relation", [])]
    return []


# ------------------- ID -> Title resolver (cached) -------------------
class PageTitleResolver:
    def __init__(self, title_prop_guess: str = "Name"):
        self.cache: Dict[str, str] = {}
        self.title_prop_guess = title_prop_guess

    def resolve(self, page_id: str) -> str:
        if page_id in self.cache:
            return self.cache[page_id]

        page = get_page(page_id)
        props = page.get("properties", {})

        title = get_title_prop(props, self.title_prop_guess)

        # Fallback: first title prop
        if not title:
            for v in props.values():
                if v.get("type") == "title":
                    title = plain_text(v.get("title", []))
                    break

        title = title.strip() or f"(untitled-{page_id[:8]})"
        self.cache[page_id] = title
        return title

class PageUrlResolver:
    """
    Resolve Notion page ID -> its Notion URL (cached).
    """
    def __init__(self):
        self.cache: Dict[str, str] = {}

    def resolve(self, page_id: str) -> str:
        if page_id in self.cache:
            return self.cache[page_id]
        page = get_page(page_id)
        url = page.get("url") or ""
        self.cache[page_id] = url
        return url


# --------------------------- Dedupe (UF) ---------------------------
class UnionFind:
    def __init__(self):
        self.parent: Dict[str, str] = {}
        self.rank: Dict[str, int] = {}

    def add(self, x: str):
        if x not in self.parent:
            self.parent[x] = x
            self.rank[x] = 0

    def find(self, x: str) -> str:
        self.add(x)
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, a: str, b: str):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1


def pick_canonical(names: List[str], prefer: Optional[Set[str]] = None) -> str:
    """
    Prefer container names when possible, else shortest then alphabetical.
    """
    prefer = prefer or set()
    preferred = [n for n in names if n in prefer]
    pool = preferred if preferred else names
    return sorted(pool, key=lambda s: (len(s), s.lower()))[0]


# ---------------------- Alias normalization (safety) ----------------------
def normalized_aliases(name: str) -> List[str]:
    """
    Conservative alias variants to catch human errors without exploding aliases:
    - lowercase
    - punctuation removed
    - whitespace collapsed
    """
    variants: Set[str] = set()
    s = (name or "").strip()
    if not s:
        return []

    low = s.lower()
    if low != s:
        variants.add(low)

    no_punct = re.sub(r"[^\w\s]", "", s).strip()
    if no_punct and no_punct != s:
        variants.add(no_punct)

    collapsed = re.sub(r"\s+", " ", s).strip()
    if collapsed and collapsed != s:
        variants.add(collapsed)

    return sorted(variants)


# ------------------------- Obsidian writing -------------------------
def safe_filename(name: str) -> str:
    name = (name or "").strip()
    name = re.sub(r'[\\/:"*?<>|]+', "_", name)
    name = re.sub(r"\s+", " ", name)
    return (name[:120] if name else "Untitled") + ".md"


def wikilink(name: str) -> str:
    return f"[[{name}]]"


def write_md_note(out_dir: Path, title: str, frontmatter: Dict[str, Any]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / safe_filename(title)

    lines: List[str] = ["---"]
    for k, v in frontmatter.items():
        if v is None or v == "" or v == []:
            continue
        if isinstance(v, list):
            lines.append(f"{k}:")
            for item in v:
                lines.append(f"  - {item}")
        else:
            lines.append(f"{k}: {v}")
    lines.append("---\n")
    lines.append(f"# {title}\n")
    # 👇 ADD THIS: render Notion Notes links in body
    notes = frontmatter.get("notion_notes", [])
    if notes:
        lines.append("## Notes (Notion)")
        for u in notes:
            lines.append(f"- [Open note]({u})")
        lines.append("")

    # Body links for graph edges
    parents = frontmatter.get("parents", [])
    children = frontmatter.get("children", [])

    if parents:
        lines.append("## Parents")
        for p in parents:
            lines.append(f"- {p}")
        lines.append("")

    if children:
        lines.append("## Children")
        for c in children:
            lines.append(f"- {c}")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# -------------------- Main export (deduped + aliases) --------------------
def export_deduped_obsidian_from_database_ids(
        container_db_id: str,
        entity_db_id: str,
        out_dir: str
) -> None:
    """
    Accepts DATABASE IDs, discovers their data_source_ids, queries rows,
    dedupes via Joins, and writes Obsidian notes.
    """
    # Discover data_source_ids
    container_db = get_database(container_db_id)
    entity_db = get_database(entity_db_id)

    container_ds_id = pick_data_source_id(container_db)
    entity_ds_id = pick_data_source_id(entity_db)

    # (Optional) show schemas to confirm
    container_ds = get_data_source(container_ds_id)
    entity_ds = get_data_source(entity_ds_id)

    print("Container data_source_id:", container_ds_id)
    print("Container properties:", list(container_ds.get("properties", {}).keys()))
    print("Entity data_source_id:", entity_ds_id)
    print("Entity properties:", list(entity_ds.get("properties", {}).keys()))

    # Query rows
    resolver = PageTitleResolver("Name")
    containers = query_data_source_all(container_ds_id)
    entities = query_data_source_all(entity_ds_id)

    print("Container rows:", len(containers))
    print("Entity rows:", len(entities))

    # --- Dedupe union via Joins (by NAME) ---
    uf = UnionFind()
    container_names: Set[str] = set()
    all_names: Set[str] = set()

    container_records: List[Dict[str, Any]] = []
    entity_records: List[Dict[str, Any]] = []

    # Containers
    for row in containers:
        props = row.get("properties", {})
        name = get_title_prop(props, "Name").strip()
        if not name:
            continue

        game = get_multi_select(props, "Game")
        level = get_multi_select(props, "Level")
        child_ids = get_relation_ids(props, "Child")
        joins_ids = get_relation_ids(props, "Joins")
        notes_ids = get_relation_ids(props, "Notes")

        child_names = [resolver.resolve(pid) for pid in child_ids]
        joins_names = [resolver.resolve(pid) for pid in joins_ids]

        container_names.add(name)
        all_names.add(name)
        for j in joins_names:
            all_names.add(j)

        container_records.append({
            "name": name,
            "game": game,
            "level": (level[0] if level else None),
            "children": child_names,
            "joins": joins_names,
            "notes_ids": notes_ids
        })

        uf.add(name)
        for j in joins_names:
            uf.union(name, j)

    # Entities
    for row in entities:
        props = row.get("properties", {})
        name = get_title_prop(props, "Name").strip()
        if not name:
            continue

        game = get_multi_select(props, "Game")
        parent_ids = get_relation_ids(props, "Parent")
        joins_ids = get_relation_ids(props, "Joins")
        parent_names = [resolver.resolve(pid) for pid in parent_ids]
        joins_names = [resolver.resolve(pid) for pid in joins_ids]
        notes_ids = get_relation_ids(props, "Notes")

        all_names.add(name)
        for j in joins_names:
            all_names.add(j)

        entity_records.append({
            "name": name,
            "game": game,
            "parents": parent_names,
            "joins": joins_names,
            "notes_ids": notes_ids
        })

        uf.add(name)
        for j in joins_names:
            uf.union(name, j)

    for n in all_names:
        uf.add(n)

    # Groups root -> names
    groups: Dict[str, List[str]] = {}
    for n in all_names:
        root = uf.find(n)
        groups.setdefault(root, []).append(n)

    # Canonical + base aliases
    canonical_of: Dict[str, str] = {}
    base_aliases_for_canon: Dict[str, List[str]] = {}

    for _, names in groups.items():
        uniq = sorted(set(names))
        canon = pick_canonical(uniq, prefer=container_names)
        for n in uniq:
            canonical_of[n] = canon
        base_aliases_for_canon[canon] = [n for n in uniq if n != canon]

    # Aggregate metadata into canonical nodes
    agg: Dict[str, Dict[str, Any]] = {}

    def ensure(canon: str):
        if canon not in agg:
            agg[canon] = {
                "type_set": set(),
                "game_set": set(),
                "level": None,
                "parents_set": set(),
                "children_set": set(),
                "notes_ids": set(),
                "notes_source": None,  # None | "container" | "entity"

            }

    for rec in container_records:
        canon = canonical_of[rec["name"]]
        ensure(canon)
        a = agg[canon]
        a["type_set"].add("container")
        a["game_set"].update(rec["game"])
        if rec["level"] and not a["level"]:
            a["level"] = rec["level"]
        if rec.get("notes_ids"):
            a["notes_ids"].update(rec["notes_ids"])
            a["notes_source"] = "container"
        for ch in rec["children"]:
            a["children_set"].add(canonical_of.get(ch, ch))

    for rec in entity_records:
        canon = canonical_of[rec["name"]]
        ensure(canon)
        a = agg[canon]
        a["type_set"].add("entity")
        a["game_set"].update(rec["game"])
        # Use entity notes only if container didn't provide any
        if rec.get("notes_ids") and a["notes_source"] is None:
            a["notes_ids"].update(rec["notes_ids"])
            a["notes_source"] = "entity"
        for p in rec["parents"]:
            a["parents_set"].add(canonical_of.get(p, p))

    # Final aliases = join-derived + normalized variants + uniqueness check
    alias_to_canon: Dict[str, str] = {}
    final_aliases_for_canon: Dict[str, List[str]] = {}

    for canon in agg.keys():
        aliases: Set[str] = set(base_aliases_for_canon.get(canon, []))

        aliases.update(normalized_aliases(canon))
        for a_ in list(aliases):
            aliases.update(normalized_aliases(a_))

        aliases.discard(canon)
        aliases_list = sorted(aliases, key=lambda s: (len(s), s.lower()))
        final_aliases_for_canon[canon] = aliases_list

        for a_ in aliases_list:
            if a_ in alias_to_canon and alias_to_canon[a_] != canon:
                other = alias_to_canon[a_]
                raise RuntimeError(
                    f"Alias conflict: {a_!r} maps to both {other!r} and {canon!r}. "
                    f"Fix Notion data or adjust alias normalization."
                )
            alias_to_canon[a_] = canon

    # Write canonical notes
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    wrote = 0
    # --- Resolve Notion Notes page IDs -> URLs (cached) ---
    url_resolver = PageUrlResolver()
    for canon, a in agg.items():
        type_set = a["type_set"]
        if type_set == {"container"}:
            type_val = "container"
        elif type_set == {"entity"}:
            type_val = "entity"
        else:
            type_val = "container+entity"

        games = sorted(a["game_set"])
        parents = sorted(x for x in a["parents_set"] if x != canon)
        children = sorted(x for x in a["children_set"] if x != canon)

        fm: Dict[str, Any] = {
            "type": type_val,
            "game": games,
            "level": a["level"],
            "parents": [wikilink(p) for p in parents],
            "children": [wikilink(c) for c in children],
        }
        # 👇 ADD THIS: Notes relation -> Notion URLs
        notes_urls = [url_resolver.resolve(pid) for pid in sorted(a["notes_ids"])]
        notes_urls = [u for u in notes_urls if u]
        if notes_urls:
            fm["notion_notes"] = notes_urls

        aliases = final_aliases_for_canon.get(canon, [])
        if aliases:
            fm["aliases"] = aliases

        write_md_note(out_path, canon, fm)
        wrote += 1

    print(f"Containers in Notion: {len(container_records)}")
    print(f"Entities in Notion:   {len(entity_records)}")
    print(f"Canonical notes written: {wrote}")
    print(f"Resolved related pages (cache): {len(resolver.cache)}")
    print(f"Output folder: {out_path.resolve()}")


# ----------------------------- Run -----------------------------
if __name__ == "__main__":
    # Fill these in:
    CONTAINER_DB_ID = "2d9a688e32e280f2971af35b861b5812"
    ENTITY_DB_ID = "2d9a688e32e28035ac63dd88c7320d18"

    OUT_DIR = "/Users/mathsu/Documents/Hoyoverse/Hoyoverse Graph/HoyoverseTerms"
    export_deduped_obsidian_from_database_ids(CONTAINER_DB_ID, ENTITY_DB_ID, OUT_DIR)
