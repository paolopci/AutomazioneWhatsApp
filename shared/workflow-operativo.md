# Workflow Operativo

## Principio iniziale

Leggi sempre `AGENTS.md` come prima azione di ogni nuova richiesta sul progetto, prima di analisi, piano, uso tool o modifiche.

Unica eccezione: se `AGENTS.md` non esiste e l'utente ha detto esattamente `crea AGENTS.md`, segui la procedura di creazione definita dalla skill `agents-md-refactor`, poi leggi il nuovo `AGENTS.md`.

Se `AGENTS.md` non è stato letto nella richiesta corrente:
- non proporre checklist;
- non usare tool;
- non eseguire attività operative.

Se l'utente nomina esplicitamente MCP o uno specifico server MCP:
- verifica dopo la lettura di `AGENTS.md` se i server MCP nominati dall'utente sono configurati correttamente per il repository, la solution o l'ambiente corrente;
- verifica questi controlli esatti: server disponibile, path/root configurati per il `cwd` corrente, credenziali presenti quando il server MCP non è anonimo o richiede autenticazione configurata;
- se uno dei controlli MCP fallisce, dichiara in modo esplicito quale server manca o quale controllo è fallito;
- non correggere automaticamente la configurazione MCP;
- chiedi all'utente di rispondere esattamente `autorizzo correzione MCP`;
- procedi solo dopo risposta esatta `autorizzo correzione MCP`.

## Decisione iniziale per i task complessi

Presenta la scelta `A/B/C/D` soltanto se il task coinvolge almeno una di queste condizioni:

- più layer o più fasi coordinate;
- sicurezza, autenticazione o autorizzazione;
- contratti API, schema dati o database;
- rischio di breaking change;
- requisiti ambigui che cambiano materialmente la soluzione;
- lavoro abbastanza ampio da richiedere pianificazione strutturata.

Per task piccoli, locali, chiari e reversibili non presentare la scelta: analizza il perimetro e procedi secondo l'autorizzazione già fornita.

Per i task complessi:

1. verifica se la skill `$dotnet-task-decomposition` è disponibile nella sessione corrente;
2. presenta `A` e `D` in ogni caso;
3. presenta `B` e `C` solo se `$dotnet-task-decomposition` è disponibile;
4. marca con `(raccomandata)` una sola opzione tra quelle disponibili;
5. fermati e attendi una sola scelta dell'utente.

Schema completo, quando la skill è disponibile:

- `A. Applica Modalità piano`
- `B. Applica Modalità piano e la skill $dotnet-task-decomposition`
- `C. Applica la skill $dotnet-task-decomposition`
- `D. Nessuna delle due`

Se `$dotnet-task-decomposition` non è disponibile, mostra soltanto:

- `A. Applica Modalità piano`
- `D. Nessuna delle due`

Determina l'opzione raccomandata con questi criteri:

- raccomanda `A` per pianificazione conversazionale di un task ampio o ambiguo;
- raccomanda `B` per task grande, rischioso, multi-fase o multi-layer che richiede anche `PRD` e `PLAN`;
- raccomanda `C` per un task complesso ma già definito che richiede disciplina documentale nel repository;
- raccomanda `D` quando non serve uno dei due meccanismi disponibili.

Regole obbligatorie:

- non presentare opzioni non disponibili;
- non marcare più di una risposta come `(raccomandata)`;
- non reinterpretare la scelta dell'utente;
- se viene scelta `A` o `B`, usa il meccanismo offerto dalla superficie corrente per attivare Modalità piano; se richiede un'azione dell'utente, chiedila e attendi conferma;
- se viene scelta `B` o `C`, leggi integralmente e applica `$dotnet-task-decomposition`;
- se viene scelta `D`, non usare né Modalità piano né `$dotnet-task-decomposition`.

## Esecuzione adattiva

Dopo aver definito e, quando necessario, approvato il perimetro:

- procedi autonomamente senza introdurre gate obbligatori a livello di step o item;
- usa una checklist o un piano solo quando rendono il lavoro più verificabile;
- mantieni gli aggiornamenti concisi e proporzionati al task;
- non chiedere nuove conferme per normali operazioni interne al perimetro concordato;
- fermati soltanto se servono eliminazioni, installazioni, configurazioni sensibili, nuovi permessi, breaking change o un ampliamento del perimetro;
- se una skill definisce una sequenza di proposta e conferma più specifica, applica quella sequenza alle sole modifiche governate dalla skill.

## Esecuzione e validazione

- Dopo ogni modifica significativa, valida l'esito in modo proporzionato al rischio.
- Testa e verifica il codice modificato con i controlli applicabili.
- Riformatta i file toccati quando il progetto lo richiede.
- Se un'operazione richiede accessi non disponibili, usa il meccanismo di richiesta permessi offerto dalla superficie corrente; se non esiste, segnala il blocco.
- Mantieni in italiano il contenuto del piano e dei deliverable.

## Ciclo di validazione e riparazione controllata

Dopo ogni modifica autorizzata applica questo ciclo:

1. seleziona i controlli pertinenti in base al progetto e al perimetro della modifica;
2. esegui prima il controllo più specifico capace di verificare il comportamento modificato;
3. se il controllo fallisce, diagnostica la causa prima di modificare altro;
4. applica solo la correzione minima, autorizzata e interna al perimetro;
5. riesegui il controllo fallito;
6. quando il controllo specifico passa, esegui i controlli più ampi applicabili, inclusi suite completa, build e revisione del diff.

Limiti obbligatori:

- esegui al massimo tre iterazioni di correzione dopo il primo fallimento;
- fermati prima del limite se lo stesso errore rimane invariato dopo due correzioni consecutive;
- considera invariato l'errore quando falliscono lo stesso controllo e la stessa causa radice, anche se cambiano dettagli variabili come timestamp, identificativi o numeri di riga;
- fermati se la correzione richiede dipendenze mancanti, nuovi permessi, modifiche distruttive, configurazioni sensibili, breaking change o interventi fuori perimetro;
- quando ti fermi, riporta controllo fallito, tentativi eseguiti, causa individuata, blocco e verifica rimasta incompleta;
- non dichiarare completato o verificato un task se un controllo applicabile non passa o non può essere eseguito.

Divieti:

- non disabilitare, saltare o indebolire test e controlli;
- non rimuovere o rendere meno restrittive le assertion per ottenere un esito positivo;
- non modificare codice estraneo alla causa solo per rendere verde il controllo;
- non rimuovere o riclassificare come non applicabile un controllo già selezionato dopo che è fallito, salvo una modifica del perimetro approvata dall'utente;
- non installare dipendenze o modificare configurazioni sensibili senza il permesso richiesto;
- non continuare indefinitamente in presenza dello stesso errore.

Usa il browser come controllo soltanto per task UI, quando l'applicazione è avviabile nell'ambiente corrente e sono definiti criteri di accettazione osservabili. In caso contrario, segnala che la verifica browser non è applicabile o non è stata eseguita.

## Skill

La lettura o valutazione teorica di una skill non equivale a esecuzione operativa.

Per usare operativamente una skill:
- se una skill definisce una regola di autorizzazione più specifica, applica solo quella regola specifica e non chiedere `autorizzo skill`;
- se la skill non definisce una regola di autorizzazione più specifica, chiedi all'utente di rispondere esattamente `autorizzo skill`;
- usa solo skill autorizzate e disponibili nella sessione corrente; disponibile significa presente nell'elenco skill della sessione corrente;
- quando `autorizzo skill` è richiesto, attendi la risposta esatta `autorizzo skill` prima di procedere;
- dopo l'autorizzazione valida, cioè autorizzazione specifica della skill oppure risposta esatta `autorizzo skill`, valida in 1-2 righe che l'autorizzazione è stata ricevuta correttamente.
