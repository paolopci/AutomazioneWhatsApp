# PRD

## Obiettivo

Semplificare l'automazione affinche inoltri una sola immagine dalla chat `Rosario` alla chat `Destinazione` con il minor numero possibile di passaggi applicativi.

## Problema/Contesto

Il flusso attuale trova immagini nella chat sorgente ma non completa il comando WhatsApp `Inoltra`; contiene inoltre storico, deduplicazione, filtri e strategie di recupero che l'utente ha chiesto esplicitamente di rimuovere.

## Scope

- Conservare apertura browser, ricerca della chat sorgente e selezione della chat di destinazione.
- Selezionare la prima immagine inoltrabile disponibile nella cronologia caricata di `Rosario`.
- Inoltrare l'immagine scelta a `Destinazione`.
- Ridurre il codice a un percorso lineare e messaggi di errore essenziali.

## Out of scope

- Storico degli invii, deduplicazione e calcolo hash.
- Filtro di dimensioni, visibilita, sticker o immagini nascoste.
- Scansioni ripetute, scorrimento della cronologia, fallback di menu e modalita diagnostica.
- Invii multipli, pianificazione o supporto a piu sorgenti/destinazioni.

## Requisiti funzionali

- Il bot cerca `Rosario`, individua la prima immagine inoltrabile nella vista caricata e la inoltra a `Destinazione`.
- Se un passaggio indispensabile di WhatsApp Web non e disponibile entro il timeout, il bot termina senza inviare.
- L'avvio normale resta `python whatsapp_bot.py` e `avvia_bot.bat`.

## Vincoli tecnici

- Nessuna nuova dipendenza o modifica di `ProfiloChrome/`.
- Restano attese Selenium minime per caricamento della UI e conferma dell'invio; non sono controlli funzionali aggiuntivi.
- L'invio reale richiede conferma esplicita immediatamente prima dell'esecuzione.

## Acceptance criteria

- Il codice non legge o scrive `storico_invii.json` e non usa hash, filtri immagine, scorrimento o diagnostica.
- Con una chat sorgente caricata che contiene un'immagine inoltrabile, il flusso seleziona una sola immagine e tenta un solo inoltro a `Destinazione`.
- I test automatici e il controllo sintattico passano.

## Definizione di completamento

La semplificazione e implementata, validata staticamente e con test automatici; l'invio reale e eseguito solo dopo una nuova conferma esplicita dell'utente e il relativo esito viene riportato.
