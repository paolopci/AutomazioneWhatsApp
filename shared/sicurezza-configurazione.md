# Sicurezza e Configurazione

## Obiettivo

Queste regole definiscono i controlli obbligatori di sicurezza applicativa e gestione configurazione da richiamare nei repository che le adottano.

## Regole

- Non committare segreti in file versionati come `appsettings*.json` o `launchSettings.json`.
- Per credenziali e valori sensibili usa variabili d'ambiente o user secrets.
- Separa la configurazione locale, di sviluppo e di produzione.
- Documenta i punti di configurazione sensibili senza esporre valori reali.
- Valida gli input in ingresso nel boundary applicativo corretto.
- Gestisci in modo esplicito input mancanti, non validi o fuori formato.
- Restituisci codici di stato coerenti con il risultato dell'operazione.
- Non esporre dettagli sensibili o stack trace nei messaggi destinati all'utente finale.
