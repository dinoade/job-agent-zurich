# Job Agent Zurigo

Cerca stage/internship in area Zurigo per un neolaureato in finanza (master UZH),
divisi su due canali indipendenti:

- **Canale 1 — esterno / tutta la rete**: jobs.ch (ricerca libera, qualsiasi azienda)
  + LinkedIn + Indeed.ch + JobLeads.com. Nessun filtro di azienda: copre consulenze,
  aziende piccole, qualsiasi settore.
- **Canale 2 — diretto**: solo le aziende assegnate all'inizio (114 banche/assicurazioni
  svizzere), controllate direttamente sui loro siti careers ufficiali.

Entrambi i canali applicano gli stessi filtri (config/settings.json):

- **Ruolo** (`role_keywords`, obbligatorie): intern, internship, praktikum, praktikant,
  praktikant:in, praktikantin — solo stage/internship.
- **Esclusioni** (`exclude_keywords`): scarta il titolo se contiene senior, hr, human
  resources, ib, investment banking, it, energy, robotics, marketing, ml — anche se
  soddisfa il filtro ruolo.
- **Luogo** (`location_keywords` / `canton_filter`): cantoni ZH, ZG, SH, AG, SG —
  Zurigo città e dintorni, Zugo, Sciaffusa, Baden, San Gallo e zone limitrofe (~1h di
  treno da Winterthur). Filtro a livello di cantone: in casi rari può includere
  località di quel cantone più lontane di 1h (es. Aargau occidentale).
- **Dominio** (`domain_keywords`, obbligatorie — controllate su titolo E nome
  azienda): almeno una tra banking, finance/finanz, data, process
  development/prozessentwicklung, economics/wirtschaft, compliance, controlling,
  accounting, treasury, investment, asset/wealth management, insurance, audit, risk.
  Esclude stage chiaramente di altre facoltà (medicina, pedagogia, ingegneria,
  amministrazione generica, ecc.) anche se non coperti da `exclude_keywords`.

## Come funziona (due infrastrutture diverse, per limiti tecnici reali)

Le routine cloud di Claude Code (CCR) hanno rete in uscita ristretta (solo
github.com in lettura + gli strumenti nativi WebSearch/WebFetch; jobs.ch e ntfy.sh
sono bloccati) e — testato più volte, in modi diversi — **nessuna scrittura sul repo
GitHub**, anche se il repo risulta collegato. Questo divide necessariamente il
sistema:

### Canale 1 — jobs.ch: GitHub Actions, completamente automatico

`scripts/check_jobs.py` gira su GitHub Actions (internet libero, scrittura nativa sul
repo via `GITHUB_TOKEN`) ogni 6 ore. Cerca su jobs.ch con termini liberi (praktikum,
internship, praktikant...), **non limitato a nessuna lista di aziende** — trova
qualsiasi datore di lavoro che pubblica lì. Filtra per ruolo/esclusioni/luogo,
confronta con `state/external_seen.json`, invia notifica push via **ntfy.sh** solo
per i nuovi annunci, e mantiene due file sempre aggiornati:

- [`state/external_positions.txt`](state/external_positions.txt): elenco leggibile di
  *tutte* le posizioni attualmente trovate (rigenerato ogni run, non solo le nuove).
- [`state/external_matches_log.md`](state/external_matches_log.md): log storico,
  solo aggiunte, con timestamp.

Ad ogni run lo stato salvato viene anche ripulito automaticamente dalle voci che non
rispettano più i filtri attuali (es. se cambi `exclude_keywords`, le voci ormai
escluse spariscono dal file invece di restare per sempre).

### Canale 1 (resto) + Canale 2 — routine cloud Claude Code

La stessa routine cloud copre in un'unica esecuzione ogni 6 ore:

- **LinkedIn** (Canale 1): solo tramite WebSearch (`site:linkedin.com/jobs ...`), mai
  fetch diretto — raschiare LinkedIn viola i loro termini di servizio.
- **Indeed.ch** (Canale 1): `curl`/richieste dirette bloccate da Cloudflare (403, e il
  feed RSS non esiste più), ma WebFetch su URL di ricerca costruiti
  (`ch.indeed.com/jobs?q=...&l=...`) funziona bene — verificato con risultati reali.
- **JobLeads.com** (Canale 1): la loro ricerca via URL diretto è rotta/inaffidabile
  (ignora i parametri), ma le pagine dei singoli annunci sono indicizzate — funziona
  solo via WebSearch con `site:jobleads.com ...`.
- **Le 76 aziende assegnate** (Canale 2, in
  [`config/direct_check_companies.json`](config/direct_check_companies.json), frutto
  dell'audit dell'11 agosto 2026 su tutte le 114 aziende): controllo diretto dei loro
  siti careers ufficiali, gestisce portali eterogenei (Workday, Taleo,
  SuccessFactors...) impossibili da raschiare in modo affidabile con uno script.

La routine deduplica tra tutte le fonti se la stessa posizione compare più volte, e
notifica via lo strumento nativo **PushNotification** di Claude Code (richiede Remote
Control collegato — vedi Setup).

**Limite confermato** (testato: push su `main`, push su branch `claude/*`, tool MCP
GitHub — tutti bloccati con 403): questa routine non può salvare stato né scrivere
file nel repo da quell'ambiente. Di conseguenza:

- Ogni notifica elenca gli annunci *attualmente aperti*, non solo i nuovi —
  aspettati ripetizioni finché un annuncio resta pubblicato.
- Una notifica push ha un limite fisso di ~200 caratteri: se i risultati non ci
  stanno tutti, la routine invia solo i più rilevanti. Il dettaglio completo di ogni
  run resta visibile aprendo la sessione su
  https://claude.ai/code/routines/trig_018hj6Lc29qPW2nLttzu3Ngs.
- **Nessun file .txt automatico** per queste fonti (LinkedIn/Indeed/JobLeads +
  Canale 2): quando serve, viene generato manualmente rileggendo l'ultima esecuzione
  della routine e committato nel repo — non è un aggiornamento autonomo ogni 6h.

**Scartato**: studysmart.ch è un sito di consulenza per studiare all'estero, non un
job board (probabile omonimo non pertinente).

## Setup

### 1. Notifiche push — Canale 1/jobs.ch (ntfy.sh)

1. Installa l'app **ntfy** su iOS/Android (gratuita, nessuna registrazione).
2. Nell'app, aggiungi come "subscription" questo topic (tienilo segreto, funge da password):
   ```
   zh-jobs-749009385cbe
   ```

### 2. Notifiche push — resto Canale 1 + Canale 2 (Remote Control)

1. Installa l'app **Claude** ufficiale (App Store / Play Store) e accedi con lo stesso
   account che usi per Claude Code.
2. Accetta il permesso di notifiche del sistema operativo.
3. Nel terminale Claude Code: `/config agentPushNotifEnabled=true remoteControl=true`.

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

- **Parole chiave ruolo**: modifica `role_keywords` in `config/settings.json`.
- **Esclusioni**: modifica `exclude_keywords` in `config/settings.json`.
- **Dominio (settore)**: modifica `domain_keywords` in `config/settings.json` — lascia
  vuoto `[]` per disattivare il filtro di dominio (tutti i settori, non solo finanza).
- **Luoghi**: modifica `location_keywords` / `canton_filter` in `config/settings.json`.
- **Termini di ricerca jobs.ch (Canale 1)**: modifica `BROAD_SEARCH_TERMS` in
  `scripts/check_jobs.py`.
- **Aziende del Canale 2**: modifica `config/direct_check_companies.json`.

## Test locale

```bash
cd ~/job-agent-zurich
NTFY_TOPIC="zh-jobs-749009385cbe" python3 scripts/check_jobs.py
```

## Verifica siti careers (2026-08-12)

Le 114 aziende assegnate all'inizio sono state controllate individualmente: ricerca
del sito careers ufficiale + verifica che risponda davvero (non un dominio morto).
Risultato usato per costruire il Canale 2 (`config/direct_check_companies.json`, 76
URL uniche dopo deduplica):

- **84 aziende**: sito careers diretto verificato e funzionante (proprio o del gruppo).
- **30 aziende**: nessuna pagina careers dedicata trovata — piccole succursali di
  booking/legal senza staff locale che assume; coperte comunque dal Canale 1.
- **0 link rotti** rimasti (l'unico trovato, Goldman Sachs `careers.gs.com`, è già
  stato corretto in `goldmansachs.com/careers`).

## Limiti noti

- Il Canale 1 non ha filtro di settore: include stage di qualsiasi ambito trovati su
  jobs.ch/LinkedIn/Indeed/JobLeads con le parole chiave configurate, non solo finanza.
- Le 30 aziende del Canale 2 senza sito careers dedicato non sono coperte da quel
  canale — compaiono comunque nel Canale 1 se pubblicano su uno degli aggregatori.
- Canale 2 e le fonti LinkedIn/Indeed/JobLeads del Canale 1 non hanno stato
  persistente: notificano sempre gli annunci correnti, non solo i nuovi, e non
  generano un file .txt automatico (vedi sopra).
- Queste stesse fonti si basano sul ragionamento della routine cloud, non su parsing
  strutturato: possono occasionalmente segnalare un **falso positivo** (osservato una
  volta con Globalance il 14 agosto 2026). Il prompt richiede che ogni annuncio sia
  riconducibile a un URL reale visto nella run corrente, ma non elimina il rischio del
  tutto — verifica sempre sul sito prima di candidarti.
- Il matching nel Canale 1/jobs.ch è per parola chiave su titolo/luogo, non per
  significato: in rari casi può includere falsi positivi.
