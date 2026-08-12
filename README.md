# Job Agent Zurigo

Monitora automaticamente le offerte di lavoro nelle ~114 banche/assicurazioni/aziende
finanziarie configurate in [config/companies.json](config/companies.json), filtrati per:

- **Ruolo** (config/settings.json → `role_keywords`): graduate, analyst, trainee, risk,
  audit, controlling, compliance, asset/wealth management, praktikum/internship.
- **Luogo** (config/settings.json → `location_keywords` / `canton_filter`): Canton Zurigo
  (copre Zurigo città, dintorni e Winterthur).

Ogni nuovo annuncio che passa i filtri genera una notifica push sul telefono via
[ntfy.sh](https://ntfy.sh) e viene registrato in `state/matches_log.md`.

## Come funziona (due canali complementari)

**1. Sweep automatico via jobs.ch** (`scripts/check_jobs.py`, deterministico)
   Interroga jobs.ch una volta per ognuna delle 114 aziende in `config/companies.json`
   (dati strutturati incorporati nella pagina, niente browser headless), filtra per
   azienda / ruolo / luogo, confronta con `state/seen.json` e notifica i nuovi annunci.
   Buona copertura per banche private, gestori patrimoniali e assicurazioni piccole/medie
   che pubblicano su jobs.ch.

**2. Controllo diretto del sito careers ufficiale** (eseguito dalla routine cloud stessa,
   non da uno script — vedi sotto)
   Tutte le 76 URL careers uniche verificate e funzionanti (lista in
   `config/direct_check_companies.json`, derivata dall'audit dell'11 agosto 2026 su tutte
   le 114 aziende) vengono controllate direttamente ad ogni esecuzione, non solo via
   jobs.ch: molte banche/assicurazioni non pubblicano affatto sugli aggregatori svizzeri,
   i loro annunci esistono solo sul portale proprietario (spesso Workday/Taleo/SuccessFactors,
   difficile da raschiare in modo affidabile con uno script). Per questi, la routine cloud
   usa le sue capacità di ricerca web ad ogni esecuzione, confronta con
   `state/direct_check_seen.json` e notifica i nuovi annunci allo stesso modo. Il tracking
   dello stato è per-azienda: se aggiungi una nuova azienda alla lista, la prima volta che
   viene controllata i suoi annunci correnti vengono solo salvati come baseline (nessuno
   spam), esattamente come succede per l'intero sistema al primo avvio.

**Prima esecuzione**: non invia notifiche per ogni annuncio già aperto (sarebbero decine),
imposta solo una baseline. Da lì in poi vengono segnalati solo gli annunci genuinamente
nuovi.

## Setup

### 1. Notifiche push (ntfy.sh)

1. Installa l'app **ntfy** su iOS/Android (gratuita, nessuna registrazione).
2. Nell'app, aggiungi come "subscription" questo topic (tienilo segreto, funge da password):
   ```
   zh-jobs-65f1990be081
   ```
3. Fatto: ogni notifica inviata a quel topic arriva sul telefono.

### 2. Repository GitHub

Questo progetto deve vivere in un repo GitHub (privato consigliato) perché la routine
cloud legge il codice da lì:

```bash
cd ~/job-agent-zurich
gh repo create job-agent-zurich --private --source=. --push
# oppure, senza gh cli: crea un repo vuoto su github.com, poi:
git remote add origin https://github.com/<tuo-utente>/job-agent-zurich.git
git push -u origin main
```

### 3. Routine schedulata

Una routine cloud di Claude Code gira ogni 6 ore, indipendentemente dal fatto che il tuo
Mac sia acceso: esegue `scripts/check_jobs.py` (sweep jobs.ch) e poi controlla direttamente
le 76 URL careers in `config/direct_check_companies.json`. Creata una volta sola tramite
`/schedule` — gestibile/visibile su https://claude.ai/code/routines.

Nota: controllare 76 siti eterogenei via ricerca web richiede molto più tempo di sweep
jobs.ch (pochi secondi) — aspettati esecuzioni di diversi minuti (potenzialmente 15-25).

## Modificare i filtri

- **Aggiungere/rimuovere aziende**: modifica `scripts/raw_companies.txt`, poi rigenera con
  `python3 scripts/build_companies_config.py`.
- **Parole chiave ruolo**: modifica `role_keywords` in `config/settings.json`.
- **Luoghi**: modifica `location_keywords` / `canton_filter` in `config/settings.json`.

## Test locale

```bash
cd ~/job-agent-zurich
NTFY_TOPIC="zh-jobs-65f1990be081" python3 scripts/check_jobs.py
```

## Verifica siti careers (2026-08-12)

Tutte le 114 aziende sono state controllate individualmente: ricerca del sito careers
ufficiale + verifica che risponda davvero (non un dominio morto/pagina di errore). Ogni
azienda in `config/companies.json` ha ora i campi `careers_url`, `careers_status`
(`OK` / `NO_DEDICATED_SITE`) e `careers_note`.

- **84 aziende**: sito careers diretto verificato e funzionante (proprio o del gruppo).
- **30 aziende**: nessuna pagina careers dedicata trovata — quasi sempre piccole
  succursali di booking/legal senza staff locale che assume; coperte comunque dal sweep
  jobs.ch, che è l'unico posto dove potrebbero comunque comparire annunci.
- **0 link rotti** rimasti (l'unico trovato, Goldman Sachs `careers.gs.com`, è già stato
  corretto in `goldmansachs.com/careers`).

Questi URL sono stati usati per generare `config/direct_check_companies.json` (76 URL
uniche dopo deduplica — alcune aziende dello stesso gruppo condividono lo stesso portale,
es. le tre entità Zurich Insurance o UBS AG/UBS Switzerland AG), controllate direttamente
dalla routine cloud ad ogni esecuzione oltre allo sweep jobs.ch.

## Limiti noti

- Le 30 aziende senza sito careers dedicato (vedi audit sopra) restano coperte solo da
  jobs.ch — se in futuro attivano un portale proprio va aggiunto a mano a
  `config/direct_check_companies.json`.
- Il controllo diretto dei 76 siti si basa sul ragionamento/ricerca web della routine
  cloud, non su parsing strutturato: più robusto ai cambi di struttura del sito rispetto a
  uno scraper scritto a mano, ma meno deterministico — è possibile occasionalmente perdere
  o segnalare in ritardo qualche annuncio.
- Il matching azienda→annuncio nello sweep jobs.ch è basato su parole chiave estratte dal
  nome legale; in rari casi può includere falsi positivi (mitigato dal filtro ruolo+luogo).
