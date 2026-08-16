"""Funzioni condivise tra check_jobs.py (Canale 1, jobs.ch) e check_direct.py (Canale 2, siti aziendali diretti)."""
import re
import sys
import unicodedata

import requests


def strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
    )


def norm(s: str) -> str:
    return strip_accents(s or "").lower()


def location_matches(job: dict, settings: dict) -> bool:
    for loc in job.get("locations") or []:
        if loc.get("cantonCode") in settings["canton_filter"]:
            return True
    place = norm(job.get("place", ""))
    return any(norm(kw) in place for kw in settings["location_keywords"])


def role_matches(title: str, settings: dict) -> bool:
    t = norm(title)
    for kw in settings["role_keywords"]:
        if re.search(r"\b" + re.escape(norm(kw)) + r"\b", t):
            return True
    return False


def role_excluded(title: str, settings: dict) -> bool:
    t = norm(title)
    for kw in settings.get("exclude_keywords", []):
        if re.search(r"\b" + re.escape(norm(kw)) + r"\b", t):
            return True
    return False


def domain_matches(title: str, company_name: str, settings: dict) -> bool:
    domain_keywords = settings.get("domain_keywords")
    if not domain_keywords:
        return True  # nessun filtro di dominio configurato
    text = norm(f"{title} {company_name}")
    for kw in domain_keywords:
        if re.search(r"\b" + re.escape(norm(kw)) + r"\b", text):
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
