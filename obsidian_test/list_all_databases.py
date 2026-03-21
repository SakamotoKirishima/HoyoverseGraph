import os
import requests
from typing import Any, Dict, List, Tuple

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
NOTION_VERSION = "2025-09-03"
BASE_URL = "https://api.notion.com/v1"

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json",
}

def _plain_text(rich_text_list) -> str:
    return "".join(x.get("plain_text", "") for x in (rich_text_list or [])).strip()

def list_accessible_databases(page_size: int = 100) -> List[Tuple[str, str]]:
    """
    Returns a list of (database_title, database_id) that the integration can access.
    """
    url = f"{BASE_URL}/search"
    payload: Dict[str, Any] = {
        "page_size": page_size,
        "filter": {"property": "object", "value": "database"},
        # Optional: sort by last edited
        "sort": {"direction": "descending", "timestamp": "last_edited_time"},
    }

    out: List[Tuple[str, str]] = []
    while True:
        r = requests.post(url, headers=HEADERS, json=payload, timeout=60)
        if not r.ok:
            print("Status:", r.status_code)
            print("Body:", r.text)
            r.raise_for_status()

        data = r.json()
        for item in data.get("results", []):
            # item["object"] should be "database" due to the filter
            db_id = item["id"]
            title = _plain_text(item.get("title", [])) or "(Untitled database)"
            out.append((title, db_id))

        next_cursor = data.get("next_cursor")
        if not next_cursor:
            break
        payload["start_cursor"] = next_cursor

    return out

if __name__ == "__main__":
    dbs = list_accessible_databases()
    print(f"Found {len(dbs)} databases:\n")
    for title, db_id in dbs:
        print(f"- {title}: {db_id}")
