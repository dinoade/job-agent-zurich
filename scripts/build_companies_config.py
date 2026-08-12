"""One-off helper: turns raw_companies.txt into config/companies.json.

Not run by the scheduled workflow — only used to (re)generate the company
list when raw_companies.txt is edited by hand.
"""
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_FILE = ROOT / "scripts" / "raw_companies.txt"
OUT_FILE = ROOT / "config" / "companies.json"

LEGAL_TOKENS = {
    "ag", "sa", "s.a.", "ltd", "ltd.", "limited", "plc", "gmbh", "co", "co.",
    "corp", "corporation", "inc", "inc.", "n.a.", "na", "se", "n.v.", "nv",
    "a/s", "aktiengesellschaft", "bank", "banque", "bancshares", "group",
    "international", "europe", "designated", "activity", "company",
    "versicherung", "versicherungs", "gesellschaft", "sgesellschaft",
    "zweigniederlassung", "succursale", "niederlassung", "branch", "schweiz",
    "suisse", "switzerland", "de", "di", "du", "des", "the", "und", "&",
    "for", "of", "und/oder", "fur", "für", "privatbank", "private", "bhf",
}

LOCATION_TOKENS = {
    "zurich", "zürich", "winterthur", "london", "paris", "frankfurt",
    "dublin", "madrid", "brussels", "brüssel", "evere", "munich", "münchen",
    "luxembourg", "luxemburg", "vienna", "wien", "hannover", "düsseldorf",
    "antwerpen", "guernsey", "malta", "valetta", "gibraltar", "cham", "zug",
    "wallisellen", "opfikon", "nürensdorf", "sioux", "falls", "columbus",
    "peking", "beijing", "montrouge", "saint-ouen", "courbevoie", "am",
    "main", "a.m.", "leudelange", "ballerup", "st.", "julians", "kloten",
}

STOPWORDS = LEGAL_TOKENS | LOCATION_TOKENS


def strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
    )


def clean_search_term(primary: str) -> str:
    words = primary.split()
    while words and words[-1].strip(".,").lower() in LEGAL_TOKENS:
        words.pop()
    return " ".join(words) if words else primary


def match_keywords(full_name: str) -> list:
    tokens = re.findall(r"[A-Za-zÀ-ÿ.'\-]+", full_name)
    keywords = []
    for t in tokens:
        tl = t.strip(".,").lower()
        if len(tl) < 4:
            continue
        if tl in STOPWORDS:
            continue
        norm = strip_accents(tl)
        if norm not in keywords:
            keywords.append(norm)
    return keywords


def main():
    lines = [l.strip() for l in RAW_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
    companies = []
    for full_name in lines:
        primary = full_name.split(",")[0].strip()
        search_term = clean_search_term(primary)
        keywords = match_keywords(full_name)
        if not keywords:
            keywords = [strip_accents(primary.split()[0].lower())]
        companies.append({
            "full_name": full_name,
            "search_term": search_term,
            "match_keywords": keywords,
        })
    OUT_FILE.write_text(json.dumps(companies, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(companies)} companies to {OUT_FILE}")


if __name__ == "__main__":
    main()
