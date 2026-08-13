# Job Agent Zurigo

Monitora automaticamente le offerte di lavoro nelle ~114 banche/assicurazioni/aziende
finanziarie configurate in [config/companies.json](config/companies.json), filtrati per:

- **Ruolo** (config/settings.json → `role_keywords`): graduate, analyst, trainee, risk,
  audit, controlling, compliance, asset/wealth management, praktikum/internship.
- **Luogo** (config/settings.json → `location_keywords` / `canton_filter`): Canton Zurigo
  (copre Zurigo città, dintorni e Winterthur).

## Come funziona (due canali complementari, su due infrastrutture diverse)

Le routine cloud di Claude Code (CCR) hanno rete in uscita ristretta (solo
github.com read + gli strumenti nativi WebSearch/WebFetch; jobs.ch e ntfy.sh sono
bloccati) e — al momento — nessuna scrittura sul repo GitHub anche se collegato. Per
questo il sistema è diviso su due infrastrutture con caratteristiche complementari:

**1. Sweep via jobs.ch → GitHub Actions** (`scripts/check_jobs.py`, deterministico)
   Gira su GitHub Actions (internet libero, scrittura nativa sul repo via
   `GITHUB_TOKEN`), ogni 6 ore. Interroga jobs.ch una volta per ognuna delle 114
   aziende in `config/companies.json`, filtra per azienda/ruolo/luogo, confronta con
   `state/seen.json`, invia notifica push via **ntfy.sh** per i nuovi annunci e
   registra tutto in `state/matches_log.md`. Solo i nuovi annunci notificano — stato
   persistente affidabile.

**2. Controllo diretto dei siti careers ufficiali → routine cloud Claude Code**
   Le 76 URL careers uniche verificate (in `config/direct_check_companies.json`,
   frutto dell'audit dell'11 agosto 2026 su tutte le 114 aziende) vengono controllate
   ogni 6 ore dalla routine cloud, che usa ricerca/lettura web per gestire portali
   eterogenei (Workday, Taleo, SuccessFactors...) impossibili da raschiare in modo
   affidabile con uno script generico. Notifica via lo strumento nativo
   **PushNotification** di Claude Code (richiede Remote Control collegato — vedi
   Setup). **Limite confermato** (testato: push su `main`, push su branch `claude/*`,
   tool MCP GitHub — tutti bloccati con 403): questa routine non può salvare stato né
   scrivere nel repo da quell'ambiente. Di conseguenza:
   - Ogni notifica elenca gli annunci *attualmente aperti*, non solo i nuovi —
     aspettati ripetizioni finché un annuncio resta pubblicato.
   - Una notifica push ha un limite fisso di ~200 caratteri: se i risultati non ci
     stanno tutti, la routine invia solo i più rilevanti (priorità: graduate/analyst
     program → internship/praktikum → risk/audit/compliance → asset/wealth
     management → resto), non l'elenco completo. Il dettaglio completo di ogni run
     resta visibile solo aprendo la sessione su
     https://claude.ai/code/routines/trig_018hj6Lc29qPW2nLttzu3Ngs.

## Setup

### 1. Notifiche push — canale jobs.ch (ntfy.sh)

1. Installa l'app **ntfy** su iOS/Android (gratuita, nessuna registrazione).
2. Nell'app, aggiungi come "subscription" questo topic (tienilo segreto, funge da password):
   ```
   zh-jobs-65f1990be081
   ```

### 2. Notifiche push — canale controllo diretto (Remote Control)

1. Installa l'app **Claude** ufficiale (App Store / Play Store) e accedi con lo stesso
   account che usi per Claude Code.
2. Accetta il permesso di notifiche del sistema operativo.
3. Nel terminale Claude Code: `/config` → attiva "Push when Claude decides".
4. Avvia una sessione remota: `claude remote-control` (una tantum, poi resta collegato).

### 3. Repository GitHub

```bash
cd ~/job-agent-zurich
gh repo create job-agent-zurich --public --source=. --push
# oppure, senza gh cli: crea un repo su github.com, poi:
git remote add origin https://github.com/<tuo-utente>/job-agent-zurich.git
git push -u origin main
```

Nota: il repo deve essere accessibile in lettura dalla routine cloud (GitHub collegato
su claude.ai/customize/connectors) e in scrittura da GitHub Actions (automatico via
`GITHUB_TOKEN`, nessun setup aggiuntivo necessario).

### 4. Attivare i due scheduler

- **GitHub Actions**: si attiva da solo appena il file
  [.github/workflows/check-jobs.yml](.github/workflows/check-jobs.yml) è nel repo su
  GitHub (branch `main`) — verificabile nella tab "Actions" del repo.
- **Routine cloud**: creata una volta sola tramite `/schedule` — gestibile/visibile su
  https://claude.ai/code/routines.

## Modificare i filtri

- **Aggiungere/rimuovere aziende**: modifica `scripts/raw_companies.txt`, poi rigenera con
  `python3 scripts/build_companies_config.py`.
- **Parole chiave ruolo**: modifica `role_keywords` in `config/settings.json`.
- **Luoghi**: modifica `location_keywords` / `canton_filter` in `config/settings.json`.
- **Siti careers diretti**: modifica `config/direct_check_companies.json`.

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
es. le tre entità Zurich Insurance o UBS AG/UBS Switzerland AG).

## Limiti noti

- Le 30 aziende senza sito careers dedicato restano coperte solo da jobs.ch — se in
  futuro attivano un portale proprio va aggiunto a mano a
  `config/direct_check_companies.json`.
- Il controllo diretto dei 76 siti (canale 2) non ha stato persistente: notifica sempre
  tutti gli annunci correnti, non solo i nuovi (vedi sopra).
- Il matching azienda→annuncio nello sweep jobs.ch è basato su parole chiave estratte dal
  nome legale; in rari casi può includere falsi positivi (mitigato dal filtro ruolo+luogo).
