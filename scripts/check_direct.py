"""Controllo diretto dei siti careers delle aziende assegnate e notifica via ntfy.sh.

Uso:
    python3 scripts/check_direct.py

Per ognuna delle aziende in config/direct_check_companies.json, prova a
leggere la pagina careers e (best-effort) le API JSON note di alcune
piattaforme ATS comuni (es. Workday), cercando link/annunci il cui testo
soddisfa i filtri di ruolo/esclusioni/dominio in config/settings.json.

Nessuna IA coinvolta: e' un parsing per parole chiave, non per significato.
Molti portali (Workday incluso quando la pagina e' renderizzata solo via
JavaScript, SuccessFactors, Taleo, Phenom...) non espongono annunci nel solo
HTML statico scaricato con requests: per quelle aziende questo script
tipicamente trova 0 risultati anche quando ci sono posizioni aperte. Vedi
README per i limiti noti. Mantiene stato persistente in
state/direct_check_seen.json e notifica solo i NUOVI annunci rispetto
all'ultima run.
"""
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from common import domain_matches, norm, role_excluded, role_matches, send_ntfy

ROOT = Path(__file__).resolve().parent.parent
SETTINGS_FILE = ROOT / "config" / "settings.json"
COMPANIES_FILE = ROOT / "config" / "direct_check_companies.json"
STATE_FILE = ROOT / "state" / "direct_check_seen.json"
LOG_FILE = ROOT / "state" / "direct_check_matches_log.md"
POSITIONS_FILE = ROOT / "state" / "direct_check_positions.txt"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

# Testi di link puramente di navigazione (pagine categoria, non annunci
# specifici) da scartare anche se contengono una parola chiave di ruolo.
NAV_TEXT_BLOCKLIST = {
    "praktikum", "praktika", "praktikant", "praktikanten", "praktikantinnen",
    "internship", "internships", "internship program", "internship programs",
    "jobs", "career", "careers", "karriere", "karrieren",
    "stellenangebote", "offene stellen", "open positions", "open positions overview",
    "search jobs", "view all jobs", "alle jobs", "alle stellen", "job search",
    "explore careers", "students", "graduates", "students & graduates",
    "studenten", "studenten & praktikanten", "students and graduates",
    "internship programme", "internship programmes", "internship program overview",
}

# Aziende globali pubblicano stage anche fuori Svizzera; qui non abbiamo un
# campo "luogo" strutturato come su jobs.ch, quindi scartiamo per parola
# chiave quando il testo del link menziona esplicitamente una sede estera
# nota. Non esaustivo - solo riduzione rumore best-effort.
NON_SWISS_LOCATION_HINTS = [
    # Paesi/regioni (coprono molte citta' in un colpo solo)
    "usa", "united states", "u.s.a", "united kingdom", "great britain",
    "germany", "deutschland", "france", "italy", "italia", "spain", "espana",
    "portugal", "poland", "polska", "ireland", "netherlands", "belgium",
    "austria", "sweden", "denmark", "norway", "finland", "hungary", "greece",
    "india", "china", "japan", "australia", "canada", "brazil", "mexico",
    "russia", "turkey", "israel", "egypt", "nigeria", "south africa",
    "saudi arabia", "qatar", "emirates", "indonesia", "philippines",
    "vietnam", "thailand", "malaysia", "south korea", "argentina", "chile",
    "colombia", "peru",
    # Citta' - USA/Canada
    "new york", "houston", "dallas", "austin", "san antonio", "charlotte",
    "atlanta", "miami", "orlando", "tampa", "philadelphia", "washington dc",
    "wilmington", "delaware", "boston", "chicago", "san francisco",
    "los angeles", "seattle", "denver", "phoenix", "las vegas",
    "minneapolis", "detroit", "pittsburgh", "columbus", "indianapolis",
    "nashville", "st. louis", "kansas city", "salt lake city", "toronto",
    "montreal", "vancouver", "calgary",
    # Citta' - Europa/resto del mondo
    "frankfurt", "london", "paris", "milan", "milano", "madrid",
    "singapore", "hong kong", "dubai", "tokyo", "mumbai", "warsaw", "dublin",
    "luxembourg", "munich", "munchen", "berlin", "hamburg", "cologne",
    "brussels", "amsterdam", "rotterdam", "sydney", "melbourne", "brisbane",
    "shanghai", "beijing", "shenzhen", "seoul", "mexico city",
    "sao paulo", "rio de janeiro", "buenos aires", "johannesburg",
    "cairo", "riyadh", "doha", "abu dhabi", "istanbul", "tel aviv",
    "stockholm", "copenhagen", "oslo", "helsinki", "vienna", "wien", "prague",
    "budapest", "athens", "lisbon", "porto", "barcelona", "rome", "roma",
    "monaco",  # Principato di Monaco (piazza finanziaria comune per private banking)
    # Sigle aziendali note per centri servizi offshore, mai in Svizzera
    "gsc",  # HSBC "Global Service Centre" (India/Polonia/Sri Lanka/Malesia)
]


def has_non_swiss_location_hint(text: str) -> bool:
    t = norm(text)
    return any(re.search(r"\b" + re.escape(hint) + r"\b", t) for hint in NON_SWISS_LOCATION_HINTS)


WORKDAY_HOST_RE = re.compile(r"\.myworkdayjobs\.com$", re.IGNORECASE)


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


MAX_TITLE_LEN = 140


def truncate_title(text: str) -> str:
    """Alcuni siti wrappano un'intera card (titolo+descrizione+meta) in un
    unico <a>: qui accorciamo per leggibilita', tagliando su uno spazio."""
    if len(text) <= MAX_TITLE_LEN:
        return text
    cut = text[:MAX_TITLE_LEN].rsplit(" ", 1)[0]
    return cut + "..."


def job_id_for(url: str) -> str:
    return hashlib.sha1(url.strip().encode("utf-8")).hexdigest()[:16]


def try_workday_api(final_url: str) -> list:
    """Best-effort: se il sito e' su Workday, usa la loro API JSON di ricerca
    invece di provare a parsare l'HTML (che su Workday e' vuoto senza JS)."""
    parsed = urllib.parse.urlparse(final_url)
    if not WORKDAY_HOST_RE.search(parsed.netloc):
        return []
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        return []
    site = parts[1]
    tenant = parsed.netloc.split(".")[0]
    api_url = f"https://{parsed.netloc}/wday/cxs/{tenant}/{site}/jobs"
    try:
        resp = requests.post(
            api_url,
            json={"appliedFacets": {}, "limit": 50, "offset": 0, "searchText": ""},
            headers={**HEADERS, "Content-Type": "application/json"},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return []
    postings = data.get("jobPostings") or []
    results = []
    for p in postings:
        title = clean_text(p.get("title", ""))
        path = p.get("externalPath", "")
        if not title or not path:
            continue
        url = urllib.parse.urljoin(f"https://{parsed.netloc}", path)
        results.append({"title": title, "url": url})
    return results


def scan_html_links(html: str, base_url: str) -> list:
    """Caso classico: il titolo dell'annuncio E' il testo del link
    (<a>Finance Intern</a>)."""
    soup = BeautifulSoup(html, "html.parser")
    results = []
    seen_urls = set()
    for a in soup.find_all("a", href=True):
        text = clean_text(a.get_text(separator=" "))
        if not text or len(text) < 10:
            continue
        if text.lower() in NAV_TEXT_BLOCKLIST:
            continue
        href = a["href"].strip()
        if not href or href.startswith("#") or href.lower().startswith("javascript:"):
            continue
        url = urllib.parse.urljoin(base_url, href)
        if url in seen_urls:
            continue
        seen_urls.add(url)
        results.append({"title": text, "url": url})
    return results


LEAF_BLOCK_TAGS = ["p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "dt", "dd", "td"]


def scan_html_blocks(html: str, base_url: str) -> list:
    """Caso comune sui siti WordPress/CMS: il titolo dell'annuncio e' testo
    semplice in un blocco (es. <p><strong>Compliance Officer</strong></p>),
    e il link vero e proprio ("Find more information here") sta in un
    paragrafo SUCCESSIVO separato. scan_html_links da solo non lo trova
    perche' il testo del link e' generico ("here"/"hier"/...), mai il
    titolo. Qui si scansiona ogni blocco di testo "foglia" in ordine di
    documento, e se non ha un link proprio si cerca il link nei blocchi
    immediatamente successivi."""
    soup = BeautifulSoup(html, "html.parser")
    all_blocks = soup.find_all(LEAF_BLOCK_TAGS)
    leaf_blocks = [b for b in all_blocks if not b.find(LEAF_BLOCK_TAGS)]

    results = []
    seen_urls = set()
    n = len(leaf_blocks)
    for i, block in enumerate(leaf_blocks):
        text = clean_text(block.get_text(separator=" "))
        if not text or len(text) < 8 or len(text) > 200:
            continue
        if text.lower() in NAV_TEXT_BLOCKLIST:
            continue

        href = None
        a = block.find("a", href=True)
        if a:
            href = a["href"]
        else:
            for j in range(i + 1, min(i + 4, n)):
                a2 = leaf_blocks[j].find("a", href=True)
                if a2:
                    href = a2["href"]
                    break
        if not href:
            continue
        href = href.strip()
        if not href or href.startswith("#") or href.lower().startswith("javascript:"):
            continue

        url = urllib.parse.urljoin(base_url, href)
        key = (text.lower(), url)
        if key in seen_urls:
            continue
        seen_urls.add(key)
        results.append({"title": text, "url": url})
    return results


# Molte pagine careers sono solo una landing page "chi siamo" con un link
# verso la vera lista di annunci (spesso su un dominio diverso: Workday,
# Personio, SmartRecruiters, JobCloud...). Se il testo del link somiglia a
# uno di questi, la seguiamo (un livello soltanto) e scansioniamo anche
# quella pagina.
JOB_LISTING_LINK_HINTS = [
    "stellenangebote", "offene stellen", "open positions", "open position",
    "current openings", "job openings", "career opportunities", "vacancies",
    "search jobs", "view jobs", "view all jobs", "browse jobs", "job search",
    "unsere stellen", "aktuelle stellen", "stellenboerse", "stellenbörse",
    "karriereportal", "jobportal", "job board", "all jobs", "alle stellen",
    "praktikum", "praktika", "internship", "internships", "trainee",
    "graduate program", "graduate programme", "students", "graduates",
    "join us", "join our team", "work with us", "arbeiten bei",
]


def find_job_listing_link(html: str, base_url: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        text = norm(clean_text(a.get_text(separator=" ")))
        if not text:
            continue
        if any(hint in text for hint in JOB_LISTING_LINK_HINTS):
            href = a["href"].strip()
            if href and not href.startswith("#") and not href.lower().startswith("javascript:"):
                return urllib.parse.urljoin(base_url, href)
    return None


def scan_page(url: str) -> tuple:
    """Scarica una pagina e ne estrae i candidati con entrambi i metodi.
    Ritorna (candidati, html, url_finale) per permettere di seguire un
    eventuale link di secondo livello."""
    resp = requests.get(url, headers=HEADERS, timeout=25, allow_redirects=True)
    resp.raise_for_status()
    workday_results = try_workday_api(resp.url)
    if workday_results:
        return workday_results, resp.text, resp.url

    combined = []
    seen_urls = set()
    for cand in scan_html_links(resp.text, resp.url) + scan_html_blocks(resp.text, resp.url):
        if cand["url"] in seen_urls:
            continue
        seen_urls.add(cand["url"])
        combined.append(cand)
    return combined, resp.text, resp.url


def fetch_company_candidates(careers_url: str) -> list:
    candidates, html, final_url = scan_page(careers_url)

    listing_link = find_job_listing_link(html, final_url)
    if listing_link and listing_link != final_url:
        time.sleep(0.5)
        try:
            more_candidates, _, _ = scan_page(listing_link)
        except requests.RequestException:
            more_candidates = []
        seen_urls = {c["url"] for c in candidates}
        for cand in more_candidates:
            if cand["url"] not in seen_urls:
                seen_urls.add(cand["url"])
                candidates.append(cand)

    return candidates


def write_positions_txt(seen: dict, generated_at: str):
    entries = sorted(seen.items(), key=lambda kv: kv[1].get("seen_at", ""), reverse=True)
    lines = [
        f"Job Agent Zurigo - aziende dirette: scraper best-effort sui siti careers (aggiornato {generated_at})",
        f"Totale: {len(entries)}",
        "",
    ]
    for job_id, m in entries:
        lines.append(f"{m.get('company', '')} - {m.get('title', '')}")
        lines.append(f"  {m.get('url', '')}")
        lines.append("")
    POSITIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    POSITIONS_FILE.write_text("\n".join(lines), encoding="utf-8")


def prune_stale_entries(seen: dict, settings: dict) -> dict:
    kept = {}
    for job_id, m in seen.items():
        title = m.get("title", "")
        company = m.get("company", "")
        url = m.get("url", "")
        ok = (
            role_matches(title, settings)
            and not role_excluded(title, settings)
            and not has_non_swiss_location_hint(f"{title} {url}")
            and domain_matches(title, company, settings)
        )
        if ok:
            kept[job_id] = m
    removed = len(seen) - len(kept)
    if removed:
        print(f"Pulizia stato: rimosse {removed} voci che non rispettano piu' i filtri attuali.")
    return kept


def main():
    settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    companies = json.loads(COMPANIES_FILE.read_text(encoding="utf-8"))
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

    for company in companies:
        name = company.get("name", "")
        careers_url = company.get("careers_url", "")
        if not careers_url:
            continue
        try:
            candidates = fetch_company_candidates(careers_url)
        except requests.RequestException as e:
            errors.append(f"{name}: {e}")
            time.sleep(settings["request_delay_seconds"])
            continue

        for cand in candidates:
            title = cand["title"]
            url = cand["url"]
            if not role_matches(title, settings):
                continue
            if role_excluded(title, settings):
                continue
            if has_non_swiss_location_hint(f"{title} {url}"):
                continue
            if not domain_matches(title, name, settings):
                continue

            title = truncate_title(title)
            job_id = job_id_for(url)
            if job_id in seen_this_run:
                continue
            seen_this_run.add(job_id)

            if job_id not in seen:
                new_matches.append({
                    "id": job_id,
                    "title": title,
                    "company": name,
                    "url": url,
                })
            seen[job_id] = {
                "title": title,
                "company": name,
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
            "Job Agent Zurigo - Aziende dirette attivato",
            f"Baseline impostata con {len(new_matches)} annunci attualmente trovati sui siti aziendali. "
            f"Da ora ti avviso solo sui nuovi annunci.",
        )
    elif new_matches:
        print(f"{len(new_matches)} nuovi annunci trovati.")
        with LOG_FILE.open("a", encoding="utf-8") as f:
            for m in new_matches:
                f.write(f"- [{now_iso}] **{m['title']}** — {m['company']} — {m['url']}\n")

        lines = [f"{m['company']}: {m['title']}" for m in new_matches]
        body = "\n".join(lines)
        max_body_chars = 3800
        if len(body) > max_body_chars:
            truncated = []
            total = 0
            for line in lines:
                if total + len(line) + 1 > max_body_chars:
                    break
                truncated.append(line)
                total += len(line) + 1
            remaining = len(lines) - len(truncated)
            body = "\n".join(truncated) + f"\n... +{remaining} altri, vedi state/direct_check_matches_log.md nel repo"

        send_ntfy(
            ntfy_topic,
            f"{len(new_matches)} nuovi annunci trovati (aziende dirette)",
            body,
            priority="high",
        )
    else:
        print("Nessun nuovo annuncio in questa run.")
        send_ntfy(
            ntfy_topic,
            "Job Agent Zurigo - Aziende dirette",
            "Nessun nuovo annuncio trovato in questo giro.",
        )

    if errors:
        print(f"{len(errors)} aziende non raggiungibili in questa run:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
