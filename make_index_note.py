#!/usr/bin/env python3
"""
Create an Obsidian "tree view" for a root term by generating PROXY notes
in a separate folder. Proxy notes link only within the subtree, producing
a clean tree-shaped graph when you filter by that folder path.

Why proxies?
- If you put all descendants in one index note, Obsidian graph becomes a star.
- Proxies preserve structure: parent proxy links to child proxies, etc.

Assumes your existing exported term notes contain:
- YAML frontmatter (optional) including aliases
- A "## Children" section with wikilinks to children

Usage:
  python make_tree_view.py \
    --notes-dir "/path/to/vault/Terms" \
    --root "Schicksal" \
    --out-dir "/path/to/vault/Views/Schicksal" \
    --view-name "Schicksal View"

Then in Obsidian Graph:
  Filter: path:Views/Schicksal
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional

WIKILINK_RE = re.compile(r"\[\[([^\]\|#]+)(?:\|[^\]]+)?\]\]")
YAML_FENCE_RE = re.compile(r"^---\s*$", re.MULTILINE)

# ---------- parsing helpers ----------

def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")

def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip()).lower()

def split_frontmatter(md: str) -> Tuple[Dict[str, object], str]:
    if not md.startswith("---"):
        return {}, md
    matches = list(YAML_FENCE_RE.finditer(md))
    if len(matches) < 2:
        return {}, md
    start = matches[0].end()
    end = matches[1].start()
    yaml_block = md[start:end].strip("\n")
    body = md[matches[1].end():].lstrip("\n")

    fm: Dict[str, object] = {}
    cur_key: Optional[str] = None

    for raw in yaml_block.splitlines():
        line = raw.rstrip()
        if not line or line.strip().startswith("#"):
            continue

        if cur_key and line.lstrip().startswith("- "):
            item = line.strip()[2:].strip()
            fm.setdefault(cur_key, [])
            assert isinstance(fm[cur_key], list)
            fm[cur_key].append(item)
            continue

        if ":" in line:
            key, val = line.split(":", 1)
            key, val = key.strip(), val.strip()
            if val == "":
                fm[key] = []
                cur_key = key
            else:
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                fm[key] = val
                cur_key = None
        else:
            cur_key = None

    return fm, body

def extract_title(md: str, fallback: str) -> str:
    for line in md.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback

def extract_children(body: str) -> List[str]:
    lines = body.splitlines()
    out: List[str] = []
    in_children = False
    for line in lines:
        if line.strip().lower() == "## children":
            in_children = True
            continue
        if in_children and line.startswith("## "):
            break
        if in_children:
            for m in WIKILINK_RE.finditer(line):
                out.append(m.group(1).strip())
    return out

# ---------- build graph from existing notes ----------

def index_notes(notes_dir: Path) -> Tuple[Dict[str, Path], Dict[str, str], Dict[str, List[str]]]:
    md_files = sorted(notes_dir.rglob("*.md"))
    if not md_files:
        raise RuntimeError(f"No .md files found under {notes_dir}")

    title_to_path: Dict[str, Path] = {}
    alias_to_title: Dict[str, str] = {}

    # Pass 1: titles + aliases
    for p in md_files:
        md = read_text(p)
        fm, _body = split_frontmatter(md)
        title = extract_title(md, fallback=p.stem)
        title_to_path[title] = p

        alias_to_title[normalize(title)] = title
        aliases = fm.get("aliases", [])
        if isinstance(aliases, list):
            for a in aliases:
                if isinstance(a, str) and a.strip():
                    alias_to_title[normalize(a)] = title

    # Pass 2: edges
    edges: Dict[str, List[str]] = {t: [] for t in title_to_path}
    for title, p in title_to_path.items():
        md = read_text(p)
        _fm, body = split_frontmatter(md)
        raw_children = extract_children(body)

        seen: Set[str] = set()
        canon_children: List[str] = []
        for ch in raw_children:
            canon = alias_to_title.get(normalize(ch), ch)
            if canon in title_to_path and canon not in seen:
                seen.add(canon)
                canon_children.append(canon)
        edges[title] = canon_children

    return title_to_path, alias_to_title, edges

def resolve_root(root: str, title_to_path: Dict[str, Path], alias_to_title: Dict[str, str]) -> str:
    r = alias_to_title.get(normalize(root))
    if r:
        return r
    for t in title_to_path:
        if normalize(t) == normalize(root):
            return t
    raise SystemExit(f"Could not resolve root term: {root!r}")

def collect_subtree(root: str, edges: Dict[str, List[str]]) -> Set[str]:
    """All reachable descendants including root."""
    seen: Set[str] = set()
    stack = [root]
    seen.add(root)
    while stack:
        cur = stack.pop()
        for ch in edges.get(cur, []):
            if ch not in seen:
                seen.add(ch)
                stack.append(ch)
    return seen

# ---------- write proxy notes ----------

def safe_filename(name: str) -> str:
    # Obsidian is ok with many chars, but avoid path separators
    return name.replace("/", "∕").replace("\\", "∖").strip()

def write_proxy_note(
    out_dir: Path,
    title: str,
    real_rel_link: str,
    children: List[str],
    view_tag: str
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{safe_filename(title)}.md"

    lines: List[str] = []
    lines.append("---")
    lines.append("type: view-proxy")
    lines.append(f"view: {view_tag}")
    lines.append("---\n")
    lines.append(f"# {title}\n")
    lines.append(f"🔎 **Full note:** {real_rel_link}\n")
    if children:
        lines.append("## Children")
        for ch in children:
            lines.append(f"- [[{ch}]]")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--notes-dir", required=True, help="Folder with your real exported term notes (e.g. Terms)")
    ap.add_argument("--root", required=True, help="Root term (e.g. Schicksal)")
    ap.add_argument("--out-dir", required=True, help="Output folder for proxy notes inside your vault (e.g. Views/Schicksal)")
    ap.add_argument("--view-name", default=None, help="Optional name used in frontmatter (defaults to root)")
    ap.add_argument("--terms-link-mode", choices=["relative", "wikilink"], default="wikilink",
                    help="How the proxy links back to the real note: wikilink ([[Real Note]]) or relative markdown link")
    args = ap.parse_args()

    notes_dir = Path(args.notes_dir).expanduser()
    out_dir = Path(args.out_dir).expanduser()
    view_tag = args.view_name or args.root

    title_to_path, alias_to_title, edges = index_notes(notes_dir)
    root = resolve_root(args.root, title_to_path, alias_to_title)

    subtree = collect_subtree(root, edges)

    # Build proxy edges only within subtree
    proxy_edges: Dict[str, List[str]] = {}
    for node in subtree:
        proxy_edges[node] = [ch for ch in edges.get(node, []) if ch in subtree]

    # Write proxies
    wrote = 0
    for node in sorted(subtree, key=lambda s: s.lower()):
        if args.terms_link_mode == "wikilink":
            real_link = f"[[{node}]]"
        else:
            # relative markdown link to real file (best-effort)
            real_path = title_to_path[node]
            real_link = f"[Open real note]({real_path.as_posix()})"

        write_proxy_note(
            out_dir=out_dir,
            title=node,
            real_rel_link=real_link,
            children=proxy_edges[node],
            view_tag=view_tag
        )
        wrote += 1

    # Write a single entry-point index for the view folder
    entry = out_dir / f"{safe_filename(view_tag)} (View Index).md"
    entry_lines = [
        "---",
        "type: view-index",
        f"view: {view_tag}",
        "---\n",
        f"# {view_tag} (View)\n",
        "> This folder contains proxy notes that preserve the tree shape in Obsidian's graph.\n",
        "## Root\n",
        f"- [[{root}]]\n",
        "## How to view\n",
        f"- Open Graph → filter: `path:{out_dir.name}` (or the full relative path)\n",
    ]
    entry.write_text("\n".join(entry_lines), encoding="utf-8")

    print(f"Wrote {wrote} proxy notes to: {out_dir}")
    print(f"View entry note: {entry}")
    print("In Obsidian Graph, filter by path to this folder to see the clean subtree graph.")

if __name__ == "__main__":
    main()
