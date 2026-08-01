# Inoltro di un'immagine non ripetuta

## Obiettivo

Estendere il bot Selenium affinché, a ogni esecuzione di `avvia_bot.bat`, inoltri una sola immagine dal gruppo `Rosario` al gruppo `Destinazione`. L'immagine deve essere scelta casualmente e non deve avere lo stesso contenuto visivo di nessuna delle ultime sette immagini inviate dal bot.

## Perimetro

La logica resta in `whatsapp_bot.py`, coerentemente con la struttura attuale del progetto. Il bot considera soltanto immagini contenute nei messaggi della chat e ignora avatar, icone, sticker e video. Non vengono aggiunte dipendenze.

## Flusso

1. Avviare Chrome con il profilo dedicato e aprire WhatsApp Web.
2. Cercare e selezionare `GRUPPO_SORGENTE`, configurato come `Rosario`.
3. Individuare i messaggi contenenti immagini già caricate.
4. Se non esiste ancora un candidato utilizzabile, scorrere verso l'alto per un massimo di 20 passaggi e ripetere la scansione.
5. Leggere i byte delle immagini tramite il contesto autenticato del browser e calcolarne l'impronta SHA-256.
6. Escludere le impronte presenti nello storico degli ultimi sette invii.
7. Scegliere casualmente un candidato idoneo e inoltrare il relativo messaggio a `GRUPPO_DESTINAZIONE`.
8. Attendere la chiusura del pannello di inoltro come conferma dell'azione.
9. Solo dopo la conferma, salvare l'impronta e stampare il messaggio di successo.

## Stato persistente

Lo storico risiede in `storico_invii.json` nella root del progetto e contiene una versione del formato e una lista ordinata di massimo sette impronte. Il file viene scritto in modo atomico per evitare uno stato parziale e viene escluso da Git tramite `.gitignore`.

Un file assente equivale a uno storico vuoto. Un file non valido interrompe l'invio con un errore esplicito: il bot non deve azzerarlo automaticamente, per non perdere la garanzia anti-duplicazione.

## Identificazione delle immagini

L'identità dipende dal contenuto dell'immagine, non dall'identificativo del messaggio WhatsApp. Due messaggi differenti che contengono la stessa foto producono quindi la stessa impronta e sono considerati duplicati. Se i byte di una specifica immagine non possono essere letti, quel candidato viene ignorato senza bloccare gli altri.

## Errori e sicurezza dell'invio

Se non esistono immagini idonee entro il limite di scorrimento, il bot non invia nulla, non modifica lo storico e mostra il motivo nel terminale. Lo stesso comportamento si applica se la sorgente, la destinazione o un controllo dell'interfaccia non sono disponibili.

L'avvio manuale di `avvia_bot.bat` costituisce l'autorizzazione a un singolo invio. Non viene introdotto un secondo prompt. Dopo un invio confermato, il terminale mostra:

```text
Invio eseguito: una nuova immagine da 'Rosario' è stata inviata a 'Destinazione'.
```

Il `pause` già presente nel file batch mantiene il messaggio leggibile prima della chiusura.

## Test e criteri di accettazione

I test automatici, senza accesso a WhatsApp, verificano caricamento e salvataggio dello storico, limite di sette elementi, esclusione dei duplicati, scelta tra candidati idonei e mancato aggiornamento in caso di errore. `python -m py_compile whatsapp_bot.py` verifica la sintassi.

Il test manuale usa esclusivamente i gruppi di prova `Rosario` e `Destinazione` e deve dimostrare che:

- viene inoltrata esattamente una immagine;
- nessuna delle ultime sette impronte viene riutilizzata;
- lo storico viene aggiornato soltanto dopo l'invio;
- il messaggio di successo appare prima del `pause` del terminale;
- in assenza di candidati idonei non viene inviato alcun contenuto.
