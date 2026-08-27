# Job Agent Zurigo

Monitora i siti careers ufficiali delle aziende assegnate (banche/assicurazioni
svizzere) e notifica quando compare un nuovo stage/internship. Un solo canale,
niente ricerca su jobs.ch/LinkedIn/Indeed/JobLeads (rimossi: non affidabili
abbastanza — vedi git history se serve recuperarli).

## Come funziona

`scripts/check_direct.py` gira su **GitHub Actions ogni 6 ore**, completamente
gratis (nessuna chiave API a pagamento). Per ognuna delle 76 aziende in
[`config/direct_check_companies.json`](config/direct_check_companies.json)
(frutto dell'audit dell'11 agosto 2026 su tutte le 114 aziende assegnate
inizialmente):

1. Scarica la pagina careers ufficiale.
2. Se il sito è su piattaforma **Workday**, prova anche la loro API JSON di
   ricerca (più affidabile dell'HTML statico, che su Workday è vuoto senza
   JavaScript).
3. Cerca link il cui testo soddisfa i filtri di ruolo/esclusioni/dominio
   (vedi sotto).

Confronta con `state/direct_check_seen.json` (stato persistente reale, salvato
nel repo) e:

- Invia una notifica push via **ntfy.sh** — topic `zh-jobs-749009385cbe` —
  **solo per i nuovi annunci** rispetto all'ultima esecuzione, oppure un
  messaggio "nessun nuovo annuncio trovato" se non ce ne sono (così sai che il
  sistema è ancora vivo).
- Mantiene sempre aggiornati:
  - [`state/direct_check_positions.txt`](state/direct_check_positions.txt):
    elenco leggibile di *tutte* le posizioni attualmente trovate (rigenerato
    ogni run, non solo le nuove).
  - [`state/direct_check_matches_log.md`](state/direct_check_matches_log.md):
    log storico, solo aggiunte, con timestamp.

**Nessuna IA in questo agente — è pattern matching su parole chiave, non su
significato.** Filtri (`config/settings.json`):

- **Ruolo** (`role_keywords`, obbligatorie): intern, internship, praktikum,
  praktikant, praktikant:in, praktikantin — solo stage/internship.
- **Esclusioni** (`exclude_keywords`): scarta il titolo se contiene senior, hr,
  human resources, ib, investment banking, it, energy, robotics, marketing, ml
  + altre facoltà non pertinenti (legge, architettura, ingegneria, filosofia,
  ricerca accademica) — anche se soddisfa il filtro ruolo.
- **Dominio** (`domain_keywords`, obbligatorie — controllate su titolo E nome
  azienda): almeno una tra banking, finance/finanz, data, process
  development/prozessentwicklung, economics/wirtschaft, compliance,
  controlling, accounting, treasury, investment, asset/wealth management,
  insurance, audit, risk.

## Limiti noti (accettati per restare a costo zero, senza IA)

- **Molti portali non mostrano annunci nell'HTML statico scaricato**
  (SuccessFactors, Taleo, Phenom, e Workday quando la ricerca via API non
  risponde) — per quelle aziende lo script tipicamente trova 0 risultati anche
  quando ci sono posizioni aperte. Aziende su questi portali vanno controllate
  periodicamente a mano.
- **Nessun campo "luogo" strutturato**: per aziende globali (Deutsche Bank,
  Barclays, HSBC...) lo script scarta per parola chiave gli annunci il cui
  testo menziona esplicitamente una sede estera nota (Frankfurt, London, New
  York...), ma non è esaustivo — **verifica sempre la sede sul sito prima di
  candidarti**.
- **Nessun controllo "annuncio specifico vs pagina categoria"**: un link il
  cui testo somiglia a un titolo di stage viene incluso anche se in realtà
  porta a una pagina programma generica.
- **30 delle 114 aziende assegnate originariamente non hanno un sito careers
  dedicato** (piccole succursali senza staff locale che assume) e non sono
  coperte da questo agente.
- Matching per parola chiave su titolo/luogo/nome azienda, non per
  significato: in rari casi può includere falsi positivi o mancare falsi
  negativi.

## Setup

### 1. Notifiche push (ntfy.sh)

1. Installa l'app **ntfy** su iOS/Android (gratuita, nessuna registrazione).
2. Nell'app, aggiungi come "subscription" questo topic (tienilo segreto, funge
   da password):
   ```
   zh-jobs-749009385cbe
   ```

### 2. Repository GitHub

```bash
cd ~/job-agent-zurich
gh repo create job-agent-zurich --public --source=. --push
# oppure, senza gh cli: crea un repo su github.com, poi:
git remote add origin https://github.com/<tuo-utente>/job-agent-zurich.git
git push -u origin main
```

### 3. Attivare lo scheduler

Si attiva da solo appena il file
[.github/workflows/check-direct.yml](.github/workflows/check-direct.yml) è nel
repo su GitHub (branch `main`) — verificabile nella tab "Actions" del repo.

Il workflow legge il topic ntfy dal secret di repository `NTFY_TOPIC`
(Settings → Secrets and variables → Actions). Se non è impostato, usa il
valore di default in `config/settings.json`.

## Modificare i filtri

- **Parole chiave ruolo**: modifica `role_keywords` in `config/settings.json`.
- **Esclusioni**: modifica `exclude_keywords` in `config/settings.json`.
- **Dominio (settore)**: modifica `domain_keywords` in `config/settings.json`
  — lascia vuoto `[]` per disattivare il filtro di dominio.
- **Aziende monitorate**: modifica `config/direct_check_companies.json`.

## Test locale

```bash
cd ~/job-agent-zurich
NTFY_TOPIC="zh-jobs-749009385cbe" python3 scripts/check_direct.py
```

## Verifica siti careers (2026-08-12)

Le 114 aziende assegnate all'inizio sono state controllate individualmente:
ricerca del sito careers ufficiale + verifica che risponda davvero (non un
dominio morto). Risultato usato per costruire
`config/direct_check_companies.json` (76 URL uniche dopo deduplica):

- **84 aziende**: sito careers diretto verificato e funzionante (proprio o del
  gruppo).
- **30 aziende**: nessuna pagina careers dedicata trovata — piccole succursali
  di booking/legal senza staff locale che assume.
- **0 link rotti** rimasti (l'unico trovato, Goldman Sachs `careers.gs.com`, è
  già stato corretto in `goldmansachs.com/careers`).
