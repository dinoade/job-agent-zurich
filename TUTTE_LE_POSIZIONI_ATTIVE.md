# Tutte le posizioni attive — istantanea del 2026-08-16

Documento generato su richiesta, mettendo insieme lo stato **attuale** di tutti e
tre i canali di monitoraggio (vedi [README.md](README.md) per come funziona ogni
canale). Non è un file aggiornato automaticamente: è una foto del momento in cui è
stato creato. Per lo stato sempre aggiornato usa invece:

- [`state/external_positions.txt`](state/external_positions.txt) — Canale 1 (jobs.ch)
- [`state/direct_check_positions.txt`](state/direct_check_positions.txt) — Canale 2 (aziende dirette)
- Canale 3 (LinkedIn/Indeed/JobLeads): nessun file automatico, vedi README

**Totale posizioni trovate in questa istantanea: 9**

---

## Canale 1 — jobs.ch (ricerca libera, qualsiasi azienda)

*Aggiornato 2026-08-16 18:26 UTC*

1. **KPMG** — Internship Data Analytics Financial Services (Zürich)
   https://www.jobs.ch/en/vacancies/detail/2c40f64a-b66f-4d8c-b0c9-428ebdd71143/
2. **Crypto Finance AG** — Intern - Application Management (Zurich)
   https://www.jobs.ch/en/vacancies/detail/bd85d493-c240-4ffa-84c0-cbe6ff283543/
3. **Crypto Finance AG** — Trading Intern (Zürich)
   https://www.jobs.ch/en/vacancies/detail/c7d62dbb-fba9-4437-90f1-ee0d2fce4930/

## Canale 2 — 76 aziende dirette (scraper Python, senza IA)

*Aggiornato 2026-08-16 17:04 UTC*

4. **Zurich Insurance Group** — NextGen Tech Internship Program (sede non specificata nel testo del link)
   https://www.zurich.com/careers/nextgen-tech
5. **Deutsche Bank** — Dein Schul-, FOS- und Berufsorientierungs-Praktikum (sede non specificata nel testo del link)
   https://careers.db.com/Schuelerinnen/dein-schul-fos-und-berufsorientierungs-praktikum
6. **HSBC** — GSC: Junior Product Controller - Intern (sede non specificata nel testo del link)
   https://mycareer.hsbc.com/en_GB/external/PipelineDetail/GSC-Junior-Product-Controller-Intern/288672

⚠️ Nota specifica sul Canale 2: questi tre annunci sono passati il filtro per
parola chiave, ma **verifica sempre la sede sul sito** — lo scraper non ha un
campo "luogo" strutturato (vedi limiti nel README). "Zurich Insurance Group -
NextGen Tech" ha passato il filtro di dominio tramite il nome azienda
("insurance"), non per contenuto del titolo — controlla che sia effettivamente
un ruolo di tuo interesse prima di candidarti.

## Canale 3 — LinkedIn / Indeed / JobLeads (routine cloud, ragionamento IA)

*Da due esecuzioni della routine cloud, 2026-08-16 ~18:24–18:28 UTC. Indeed.ch
era irraggiungibile in entrambe le run per un blocco di rete temporaneo
dell'ambiente — non è detto che non ci fossero annunci anche lì.*

7. **ABB** — Finance Intern (Zürich) — via LinkedIn
   https://ch.linkedin.com/jobs/view/finance-intern-at-abb-4442668873
8. **Kanton Zürich, Statistisches Amt** — Praktikum «R Development & Data Science» (Zürich) — via JobLeads
   https://www.jobleads.com/ch/job/praktikum-r-development-data-science--zurich--e2777aca5f50b0f7af0b1cd1ada3327ea
9. **Generis AG** — Praktikant/in Standort- & Wirtschaftsförderung (Schaffhausen) — via JobLeads
   https://www.jobleads.com/ch/job/praktikant-in-standort-wirtschaftsforderung--schaffhausen--ea0f3b438dceaffdf811e9d4489d0f6dd

⚠️ Nota specifica sul Canale 3: questo canale si basa sul ragionamento della
routine cloud (WebSearch/WebFetch), non su parsing strutturato — è quello più
soggetto a falsi positivi/negativi tra i tre (vedi README, "Limiti noti"). Il
posto al Kanton Zürich e quello di Generis AG sono passati per la parola
"Wirtschaft/data", ma sono ruoli di settore pubblico/promozione economica, non
finanza tradizionale — valuta se sono comunque di tuo interesse.

---

*Generato una tantum su richiesta. Per lo stato aggiornato in automatico, guarda
i file di `state/` (Canale 1 e 2, aggiornati ogni 6h) o l'app ntfy/Claude per le
notifiche push.*
