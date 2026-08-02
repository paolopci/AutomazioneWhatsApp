# PLAN

## Checklist Generale

- [x] Analizzare richiesta, repository e vincoli locali.
- [x] Aggiornare `docs/PRD.md`.
- [x] Aggiornare `docs/PLAN.md`.
- [ ] Completare Fase 1.
- [ ] Completare Fase 2.
- [ ] Archiviare PRD/PLAN in `docs/History` a sviluppo complessivo concluso.

## Fase 1 - Riduzione del flusso di inoltro
Stato: in_progress
Scope finale: in
Tipo fase: refactoring
Obiettivo:
Ridurre `whatsapp_bot.py` a ricerca sorgente, individuazione della prima immagine inoltrabile e inoltro alla destinazione.
Attivita:
- [ ] Rimuovere storico, deduplicazione, filtri, scorrimento, diagnostica e fallback non richiesti.
- [ ] Conservare le attese Selenium minime per gli elementi indispensabili di WhatsApp Web.
- [ ] Adeguare i test al solo percorso lineare richiesto.
File o aree coinvolte:
`whatsapp_bot.py`, `tests/test_whatsapp_bot.py`
Backend impact: no
Frontend impact: no
Dipendenze:
nessuna
Validazioni:
test automatici pertinenti; `python -m py_compile whatsapp_bot.py`; ispezione del diff
Definition of done:
Il codice non contiene le funzionalita dichiarate fuori scope e i controlli automatici della fase passano.
Tracer Bullet: obbligatoria
Sub-agent: vietato
Sub-task delegabili:
nessuno
Note:
Rischio accettato dall'utente: la prima immagine inoltrabile puo non essere quella desiderata.

## Fase 2 - Verifica del singolo inoltro reale
Stato: pending
Scope finale: in
Tipo fase: verifica
Obiettivo:
Eseguire una sola volta il launcher semplificato e rilevare l'esito dell'inoltro.
Attivita:
- [ ] Richiedere una conferma esplicita immediatamente prima dell'invio reale.
- [ ] Avviare `avvia_bot.bat` una sola volta e registrare l'esito del terminale.
File o aree coinvolte:
`avvia_bot.bat`, `whatsapp_bot.py`, WhatsApp Web
Backend impact: no
Frontend impact: no
Dipendenze:
Fase 1 completata e conferma esplicita immediata dell'utente
Validazioni:
esecuzione del flusso minimo verificabile; output terminale; verifica visiva WhatsApp Web se disponibile
Definition of done:
L'output terminale conferma l'invio oppure riporta con precisione il passaggio che lo ha impedito.
Tracer Bullet: obbligatoria
Sub-agent: vietato
Sub-task delegabili:
nessuno
Note:
L'invio e un effetto esterno non reversibile.
