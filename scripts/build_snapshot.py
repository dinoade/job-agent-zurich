"""Rigenera TUTTE_LE_POSIZIONI_ATTIVE.md unendo lo stato corrente del Canale 1
(jobs.ch) e del Canale 2 (aziende dirette).

Uso:
    python3 scripts/build_snapshot.py

Il Canale 3 (LinkedIn/Indeed/JobLeads) NON e' incluso qui: gira su una routine
cloud che non puo' scrivere file nel repo (limite confermato, vedi README), quindi
non esiste uno stato automatico da cui leggere. Il documento lo segnala
esplicitamente invece di ometterlo in silenzio o mostrare dati vecchi.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXTERNAL_STATE = ROOT / "state" / "external_seen.json"
DIRECT_STATE = ROOT / "state" / "direct_check_seen.json"
OUTPUT_FILE = ROOT / "TUTTE_LE_POSIZIONI_ATTIVE.md"


def load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def sorted_entries(state: dict) -> list:
    return sorted(state.values(), key=lambda m: m.get("seen_at", ""), reverse=True)


def render_channel1(entries: list, generated_at: str) -> str:
    lines = [f"## Canale 1 — jobs.ch (ricerca libera, qualsiasi azienda)", "", f"*Aggiornato {generated_at}*", ""]
    if not entries:
        lines.append("Nessun annuncio attivo al momento.")
    for m in entries:
        place = m.get("place") or "sede non specificata"
        lines.append(f"- **{m.get('company', '')}** — {m.get('title', '')} ({place})")
        lines.append(f"  {m.get('url', '')}")
    return "\n".join(lines)


def render_channel2(entries: list, generated_at: str) -> str:
    lines = [
        "## Canale 2 — 76 aziende dirette (scraper Python, senza IA)",
        "",
        f"*Aggiornato {generated_at}*",
        "",
    ]
    if not entries:
        lines.append("Nessun annuncio attivo al momento.")
    for m in entries:
        lines.append(f"- **{m.get('company', '')}** — {m.get('title', '')}")
        lines.append(f"  {m.get('url', '')}")
    lines.append("")
    lines.append(
        "⚠️ Questo canale non ha un campo \"luogo\" strutturato e non usa IA — "
        "verifica sempre sede e pertinenza sul sito prima di candidarti "
        "(vedi \"Limiti noti\" nel README)."
    )
    return "\n".join(lines)


def main():
    external = sorted_entries(load_state(EXTERNAL_STATE))
    direct = sorted_entries(load_state(DIRECT_STATE))
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    total = len(external) + len(direct)

    doc = f"""# Tutte le posizioni attive — Canale 1 e 2

Rigenerato automaticamente ogni 6 ore da [`scripts/build_snapshot.py`](scripts/build_snapshot.py),
poco dopo l'esecuzione dei due workflow GitHub Actions. Per i dettagli su come
funziona ogni canale vedi [README.md](README.md).

**Il Canale 3 (LinkedIn/Indeed/JobLeads) non è incluso**: gira su una routine
cloud che non può scrivere file nel repo (limite tecnico confermato), quindi non
esiste uno stato persistente automatico da cui generare questa sezione. Per
quel canale restano solo le notifiche push sul telefono, o una richiesta
esplicita per un'istantanea manuale.

**Totale posizioni attive (Canale 1 + Canale 2): {total}**

---

{render_channel1(external, generated_at)}

---

{render_channel2(direct, generated_at)}

---

*Ultimo aggiornamento automatico: {generated_at}.*
"""
    OUTPUT_FILE.write_text(doc, encoding="utf-8")
    print(f"Scritto {OUTPUT_FILE} con {total} posizioni ({len(external)} Canale 1, {len(direct)} Canale 2).")


if __name__ == "__main__":
    main()
