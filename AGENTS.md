# AGENTS.md

## 1. Scopo e Ambito

Questo file contiene solo istruzioni sulla struttura del progetto e richiami ai moduli condivisi in shared/.

## 2. Regole di Collaborazione

Leggi integralmente e applica shared/regole-collaborazione.md.

## 3. Workflow Operativo

Leggi integralmente e applica shared/workflow-operativo.md prima di pianificare o modificare file.

## 4. Struttura del Progetto e Organizzazione dei Moduli

- `whatsapp_bot.py` contiene il workflow Selenium completo: configurazione del browser, ricerca chat, inoltro messaggi e punto di ingresso `main()`.
- `avvia_bot.bat` è il launcher Windows e avvia `whatsapp_bot.py` dalla directory che contiene il file batch.
- `ProfiloChrome/` viene creato a runtime da Chrome e conserva la sessione dedicata di WhatsApp Web. Trattalo come dato locale e sensibile: non committarlo, condividerlo o modificarne il contenuto.
- `__pycache__/` contiene bytecode Python generato e non è codice sorgente.

Mantieni l'automazione in `whatsapp_bot.py` finché non emerge una necessità chiara di separare i moduli. Se in futuro verrà suddivisa, mantieni distinte e mirate le responsabilità di configurazione del browser, selettori WhatsApp e orchestrazione.

## 5. Comandi di Build, Test e Sviluppo

Esegui i comandi dalla root del repository in PowerShell:

```powershell
python whatsapp_bot.py
```

Avvia Chrome con il profilo locale `ProfiloChrome` e attende la conferma dell'operatore che WhatsApp Web sia pronto. In alternativa, fai doppio clic su `avvia_bot.bat` per lo stesso workflow.

```powershell
python -m py_compile whatsapp_bot.py
```

Esegue un rapido controllo sintattico prima dei test manuali. Non esistono manifest di dipendenze o suite di test automatici dichiarati: non assumere l'esistenza di comandi package o test.

## 6. Stile del Codice e Convenzioni di Naming

Usa indentazione Python di 4 spazi e segui PEP 8 quando pratico. Denomina funzioni e variabili in `snake_case`, ad esempio `cerca_e_seleziona_chat`; usa `UPPER_SNAKE_CASE` per configurazioni modificabili come `GRUPPO_DESTINAZIONE`. Mantieni in italiano i messaggi rivolti all'utente.

Preferisci funzioni piccole, attese Selenium esplicite e gestione ristretta delle eccezioni che riporti errori utili. Centralizza i fragili selettori XPath e commenta il motivo della loro necessità quando li modifichi.

## 7. Linee Guida per i Test

Valida la sintassi con `python -m py_compile whatsapp_bot.py`. Poi esegui un test manuale controllato con una chat sorgente non sensibile e una destinazione approvata per il test. Verifica ricerca, selezione, inoltro, invio finale e chiusura del browser. Non inviare messaggi reali o sensibili esclusivamente per testare una modifica.

Per errori Selenium, ricostruisci prima l'intero flusso di esecuzione e verifica la presenza di `input()` o altri gate bloccanti prima di modificare i selettori. Usa insieme output del terminale e stato del browser per identificare la fase realmente raggiunta.

Per lo scroll della cronologia WhatsApp, non dedurre il contenitore scorrevole dal solo confronto tra `scrollHeight` e `clientHeight`. Verifica anche `getComputedStyle(elemento).overflowY`, ignora gli antenati non scorrevoli e copri con un test il passaggio al primo antenato con overflow verticale `auto` o `scroll`.

## 8. Linee Guida per Commit e Pull Request

Git non è inizializzato in questa directory, quindi non è possibile dedurre una convenzione di commit locale. Se Git verrà inizializzato, usa commit concisi all'imperativo, ad esempio `fix: wait for WhatsApp search results`. Nelle pull request descrivi le modifiche ai selettori, il perimetro del test manuale e le assunzioni sull'interfaccia di WhatsApp Web. Non includere mai `ProfiloChrome/`, codici QR, screenshot con chat private o dati personali.

## 9. Suggerimenti su Sicurezza e Configurazione

Leggi integralmente e applica shared/sicurezza-configurazione.md.

## 10. Flusso di Collaborazione

Leggi integralmente e applica shared/flusso-collaborazione.md.

## 11. Precedenza delle Istruzioni

1. `shared/workflow-operativo.md` prevale per aspetti operativi.
2. Gli altri file `shared/*.md` prevalgono per le regole condivise non operative.
3. `AGENTS.md` contiene solo istruzioni sulla struttura del progetto che non contraddicono i moduli condivisi.
