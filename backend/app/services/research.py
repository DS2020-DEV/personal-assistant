from __future__ import annotations

from typing import Any

import httpx

from .activity import log_activity


def research_topic(topic: str, extra: str = "") -> str:
    query = f"{topic} {extra}".strip()
    chunks: list[str] = []
    wiki = _wikipedia(topic)
    if wiki:
        chunks.append(wiki)
    hits = _search(query)
    if hits:
        chunks.append("Web research:\n" + hits)
    brief = "\n\n".join(chunks).strip()
    if not brief:
        brief = f"No live research available. Teach from core knowledge of: {topic}."
    log_activity("research", "brief_ready", topic)
    return brief[:9000]


def _wikipedia(topic: str) -> str:
    slug = topic.strip().replace(" ", "_")
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{slug}"
    try:
        with httpx.Client(timeout=12.0, follow_redirects=True) as client:
            response = client.get(url, headers={"User-Agent": "PersonalAssistant/1.0"})
            if response.status_code != 200:
                search = client.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={
                        "action": "opensearch",
                        "search": topic,
                        "limit": 1,
                        "namespace": 0,
                        "format": "json",
                    },
                )
                data = search.json()
                if len(data) > 1 and data[1]:
                    return _wikipedia(data[1][0])
                return ""
            payload = response.json()
            extract = payload.get("extract") or ""
            title = payload.get("title") or topic
            return f"Wikipedia — {title}:\n{extract}"
    except Exception as exc:
        log_activity("research", "wikipedia_failed", str(exc), "warn")
        return ""


def _search(query: str) -> str:
    try:
        from ddgs import DDGS

        rows = DDGS().text(query, max_results=5)
        lines = []
        for row in rows:
            title = row.get("title") or ""
            body = row.get("body") or row.get("description") or ""
            href = row.get("href") or row.get("url") or ""
            lines.append(f"- {title}: {body} ({href})")
        return "\n".join(lines)
    except Exception as exc:
        log_activity("research", "search_failed", str(exc), "warn")
        return ""
