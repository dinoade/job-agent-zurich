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

**2. Controllo diretto delle grandi banche multinazionali** (eseguito dalla routine cloud
   stessa, non da uno script — vedi sotto)
   UBS, Deutsche Bank, Goldman Sachs, JPMorgan, Morgan Stanley, HSBC, Citi, Barclays,
   Bank of America, Zurich Insurance Group e Swiss Re (lista in `config/major_banks.json`)
   quasi sempre **non** pubblicano sui portali aggregatori svizzeri: i graduate/analyst
   program li trovi solo sul loro portale proprietario (spesso Workday/Taleo, difficile da
   raschiare in modo affidabile). Per questi, la routine cloud usa le sue capacità di
   ricerca web ad ogni esecuzione, confronta con `state/major_banks_seen.json` e notifica
   i nuovi annunci allo stesso modo.

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
i portali delle grandi banche in `config/major_banks.json`. Creata una volta sola tramite
`/schedule` — gestibile/visibile su https://claude.ai/code/routines.

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

## Limiti noti

- jobs.ch è l'unica fonte per ora — copre la maggior parte delle aziende svizzere incluse
  le piccole succursali bancarie, ma non garantisce il 100% degli annunci pubblicati
  (alcune grandi banche pubblicano anche su portali propri con sistemi ATS diversi, es.
  Workday/SuccessFactors — integrabili in futuro se serve maggiore copertura).
- Il matching azienda→annuncio è basato su parole chiave estratte dal nome legale; in rari
  casi può includere falsi positivi (mitigato dal filtro ruolo+luogo).
