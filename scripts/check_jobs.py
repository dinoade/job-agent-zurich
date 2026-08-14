"""Controlla jobs.ch per nuove offerte nelle aziende configurate e notifica via ntfy.sh.

Uso:
    python3 scripts/check_jobs.py

Legge config/companies.json e config/settings.json, confronta con
state/seen.json, e notifica solo gli annunci nuovi rispetto all'ultima run.
"""
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
COMPANIES_FILE = ROOT / "config" / "companies.json"
SETTINGS_FILE = ROOT / "config" / "settings.json"
STATE_FILE = ROOT / "state" / "seen.json"
LOG_FILE = ROOT / "state" / "matches_log.md"
POSITIONS_FILE = ROOT / "state" / "positions.txt"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
    )


def norm(s: str) -> str:
    return strip_accents(s or "").lower()


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


def company_matches(job: dict, keywords: list) -> bool:
    name = norm(job.get("company", {}).get("name", ""))
    return any(kw in name for kw in keywords)


def location_matches(job: dict, settings: dict) -> bool:
    for loc in job.get("locations") or []:
        if loc.get("cantonCode") in settings["canton_filter"]:
            return True
    place = norm(job.get("place", ""))
    return any(norm(kw) in place for kw in settings["location_keywords"])


def role_matches(job: dict, settings: dict) -> bool:
    title = norm(job.get("title", ""))
    for kw in settings["role_keywords"]:
        if re.search(r"\b" + re.escape(norm(kw)) + r"\b", title):
            return True
    return False


def role_excluded(job: dict, settings: dict) -> bool:
    title = norm(job.get("title", ""))
    for kw in settings.get("exclude_keywords", []):
        if re.search(r"\b" + re.escape(norm(kw)) + r"\b", title):
            return True
    return False


def send_ntfy(topic: str, title: str, message: str, click_url: str = None, priority: str = "default"):
    if not topic:
        print("WARN: nessun NTFY_TOPIC configurato, notifica saltata.", file=sys.stderr)
        return
    headers = {
        "Title": strip_accents(title) or "Job Alert",
        "Priority": priority,
        "Tags": "briefcase",
    }
    if click_url:
        headers["Click"] = click_url
    try:
        requests.post(f"https://ntfy.sh/{topic}", data=message.encode("utf-8"), headers=headers, timeout=10)
    except requests.RequestException as e:
        print(f"WARN: invio notifica ntfy fallito: {e}", file=sys.stderr)


def write_positions_txt(seen: dict, generated_at: str):
    entries = sorted(seen.items(), key=lambda kv: kv[1].get("seen_at", ""), reverse=True)
    lines = [
        f"Job Agent Zurigo - posizioni trovate su jobs.ch (aggiornato {generated_at})",
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
        title = norm(m.get("title", ""))
        role_ok = any(
            re.search(r"\b" + re.escape(norm(kw)) + r"\b", title)
            for kw in settings["role_keywords"]
        )
        excluded = any(
            re.search(r"\b" + re.escape(norm(kw)) + r"\b", title)
            for kw in settings.get("exclude_keywords", [])
        )
        if role_ok and not excluded:
            kept[job_id] = m
    removed = len(seen) - len(kept)
    if removed:
        print(f"Pulizia stato: rimosse {removed} voci che non rispettano piu' i filtri attuali.")
    return kept


def main():
    companies = json.loads(COMPANIES_FILE.read_text(encoding="utf-8"))
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

    for company in companies:
        try:
            results = fetch_jobsch_results(company["search_term"])
        except requests.RequestException as e:
            errors.append(f"{company['full_name']}: {e}")
            time.sleep(settings["request_delay_seconds"])
            continue

        for job in results:
            if not company_matches(job, company["match_keywords"]):
                continue
            if not location_matches(job, settings):
                continue
            if not role_matches(job, settings):
                continue
            if role_excluded(job, settings):
                continue

            job_id = job.get("id")
            if not job_id:
                continue

            url = f"https://www.jobs.ch/en/vacancies/detail/{job_id}/"
            if job_id not in seen:
                new_matches.append({
                    "id": job_id,
                    "title": job.get("title", ""),
                    "company": company["full_name"],
                    "place": job.get("place", ""),
                    "url": url,
                })
            seen[job_id] = {
                "title": job.get("title", ""),
                "company": company["full_name"],
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
            body = "\n".join(truncated) + f"\n... +{remaining} altri, vedi state/matches_log.md nel repo"

        send_ntfy(
            ntfy_topic,
            f"{len(new_matches)} nuovi annunci trovati",
            body,
            priority="high",
        )
    else:
        print("Nessun nuovo annuncio in questa run.")

    if errors:
        print(f"{len(errors)} aziende non raggiungibili in questa run:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
