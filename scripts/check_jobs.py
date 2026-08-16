"""Ricerca libera su jobs.ch (qualsiasi azienda, non solo quelle configurate) e notifica via ntfy.sh.

Uso:
    python3 scripts/check_jobs.py

Cerca su jobs.ch con le stesse parole chiave di ruolo usate per il filtro
(praktikum, internship, praktikant...), su tutte le aziende che pubblicano
li' - non solo la lista storica in config/companies.json. Confronta con
state/external_seen.json e notifica solo gli annunci nuovi rispetto
all'ultima run. Fa parte del "Canale 1" (esterno/tutta la rete) insieme a
LinkedIn/Indeed/JobLeads (gestiti dalla routine cloud, vedi README).
"""
import json
import os
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import requests

from common import (
    domain_matches,
    location_matches,
    role_excluded,
    role_matches,
    send_ntfy,
)

ROOT = Path(__file__).resolve().parent.parent
SETTINGS_FILE = ROOT / "config" / "settings.json"
STATE_FILE = ROOT / "state" / "external_seen.json"
LOG_FILE = ROOT / "state" / "external_matches_log.md"
POSITIONS_FILE = ROOT / "state" / "external_positions.txt"

# Termini di ricerca jobs.ch derivati da role_keywords (solo forme senza
# caratteri speciali tipo ":" che romperebbero l'URL di ricerca).
BROAD_SEARCH_TERMS = ["praktikum", "praktikant", "praktikantin", "internship", "intern"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def extract_braced_object(html: str, marker: str):
    idx = html.find(marker)
    if idx == -1:
        return None
    start = idx + len(marker) - 1  # keep the opening brace
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(html)):
        c = html[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return html[start:i + 1]
    return None


def fetch_jobsch_results(search_term: str) -> list:
    url = "https://www.jobs.ch/en/vacancies/?term=" + urllib.parse.quote(search_term)
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    raw = extract_braced_object(resp.text, "__INIT__ = {")
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    try:
        return data["vacancy"]["results"]["main"]["results"]
    except (KeyError, TypeError):
        return []


def write_positions_txt(seen: dict, generated_at: str):
    entries = sorted(seen.items(), key=lambda kv: kv[1].get("seen_at", ""), reverse=True)
    lines = [
        f"Job Agent Zurigo - Canale 1 (esterno): ricerca libera su jobs.ch, qualsiasi azienda (aggiornato {generated_at})",
        f"Totale: {len(entries)}",
        "",
    ]
    for job_id, m in entries:
        url = m.get("url") or f"https://www.jobs.ch/en/vacancies/detail/{job_id}/"
        place = m.get("place") or "n/d"
        lines.append(f"{m.get('company', '')} - {m.get('title', '')} ({place})")
        lines.append(f"  {url}")
        lines.append("")
    POSITIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    POSITIONS_FILE.write_text("\n".join(lines), encoding="utf-8")


def prune_stale_entries(seen: dict, settings: dict) -> dict:
    """Rimuove dallo stato salvato le voci che non rispettano piu' i filtri attuali
    (es. aggiunte prima che un filtro fosse introdotto/modificato)."""
    kept = {}
    for job_id, m in seen.items():
        title = m.get("title", "")
        company = m.get("company", "")
        if role_matches(title, settings) and not role_excluded(title, settings) and domain_matches(title, company, settings):
            kept[job_id] = m
    removed = len(seen) - len(kept)
    if removed:
        print(f"Pulizia stato: rimosse {removed} voci che non rispettano piu' i filtri attuali.")
    return kept


def main():
    settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    ntfy_topic = os.environ.get("NTFY_TOPIC") or settings.get("ntfy_topic") or ""

    seen = {}
    is_first_run = not STATE_FILE.exists()
    if not is_first_run:
        seen = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        seen = prune_stale_entries(seen, settings)

    new_matches = []
    errors = []
    now_iso = datetime.now(timezone.utc).isoformat()
    seen_this_run = set()

    for term in BROAD_SEARCH_TERMS:
        try:
            results = fetch_jobsch_results(term)
        except requests.RequestException as e:
            errors.append(f"{term}: {e}")
            time.sleep(settings["request_delay_seconds"])
            continue

        for job in results:
            job_id = job.get("id")
            if not job_id or job_id in seen_this_run:
                continue
            if not location_matches(job, settings):
                continue
            title = job.get("title", "")
            company_name = job.get("company", {}).get("name", "")
            if not role_matches(title, settings):
                continue
            if role_excluded(title, settings):
                continue
            if not domain_matches(title, company_name, settings):
                continue

            seen_this_run.add(job_id)
            url = f"https://www.jobs.ch/en/vacancies/detail/{job_id}/"
            if job_id not in seen:
                new_matches.append({
                    "id": job_id,
                    "title": job.get("title", ""),
                    "company": company_name,
                    "place": job.get("place", ""),
                    "url": url,
                })
            seen[job_id] = {
                "title": job.get("title", ""),
                "company": company_name,
                "place": job.get("place", ""),
                "url": url,
                "seen_at": seen.get(job_id, {}).get("seen_at", now_iso),
            }

        time.sleep(settings["request_delay_seconds"])

    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(seen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    write_positions_txt(seen, now_iso)

    if is_first_run:
        print(f"Baseline impostata: {len(new_matches)} annunci correnti registrati (nessuna notifica inviata).")
        send_ntfy(
            ntfy_topic,
            "Job agent Zurigo attivato",
            f"Baseline impostata con {len(new_matches)} annunci attualmente aperti. "
            f"Da ora ti avviso solo sui nuovi annunci.",
        )
    elif new_matches:
        print(f"{len(new_matches)} nuovi annunci trovati.")
        with LOG_FILE.open("a", encoding="utf-8") as f:
            for m in new_matches:
                f.write(f"- [{now_iso}] **{m['title']}** — {m['company']} ({m['place']}) — {m['url']}\n")

        # ntfy.sh non ha il limite di ~200 caratteri delle push notification native:
        # mandiamo una notifica sola con la lista completa, azienda + titolo per ognuna.
        lines = [f"{m['company']}: {m['title']}" for m in new_matches]
        body = "\n".join(lines)
        max_body_chars = 3800  # margine sotto il limite pratico di ntfy.sh (~4096 byte)
        if len(body) > max_body_chars:
            truncated = []
            total = 0
            for line in lines:
                if total + len(line) + 1 > max_body_chars:
                    break
                truncated.append(line)
                total += len(line) + 1
            remaining = len(lines) - len(truncated)
            body = "\n".join(truncated) + f"\n... +{remaining} altri, vedi state/external_matches_log.md nel repo"

        send_ntfy(
            ntfy_topic,
            f"{len(new_matches)} nuovi annunci trovati",
            body,
            priority="high",
        )
    else:
        print("Nessun nuovo annuncio in questa run.")
        send_ntfy(
            ntfy_topic,
            "Job Agent Zurigo",
            "Nessun nuovo annuncio trovato in questo giro.",
        )

    if errors:
        print(f"{len(errors)} termini di ricerca falliti in questa run:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
