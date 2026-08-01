# Inoltro di un'immagine non ripetuta Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Inoltrare a ogni esecuzione una sola immagine casuale da `Rosario` a `Destinazione`, senza ripetere il contenuto delle ultime sette immagini inviate.

**Architecture:** La logica resta in `whatsapp_bot.py`, suddivisa in funzioni pure per lo storico e la selezione e in funzioni Selenium per scansione, impronta e inoltro. `storico_invii.json` conserva al massimo sette hash SHA-256 ed è aggiornato atomicamente soltanto dopo la conferma dell'invio.

**Tech Stack:** Python 3.12, libreria standard (`dataclasses`, `json`, `os`, `random`, `unittest`, `unittest.mock`), Selenium, ChromeDriver.

## Global Constraints

- Non installare nuove dipendenze.
- Conservare il workflow in `whatsapp_bot.py`.
- Considerare soltanto immagini nei messaggi; escludere avatar, icone, sticker e video.
- Scorrere verso l'alto per un massimo di 20 passaggi.
- Identificare il contenuto mediante SHA-256 dei byte dell'immagine.
- Conservare esattamente le ultime sette impronte valide in `storico_invii.json`.
- Non modificare lo storico quando l'invio non è confermato.
- Non effettuare invii WhatsApp durante i test automatici.
- Prima del test manuale con invio reale, richiedere una conferma immediata all'utente.
- Non includere in commit `ProfiloChrome/`, `storico_invii.json` o altri dati WhatsApp.

---

### Task 1: Storico persistente degli ultimi sette invii

**Files:**
- Modify: `.gitignore`
- Modify: `whatsapp_bot.py:1-29`
- Create: `tests/test_whatsapp_bot.py`

**Interfaces:**
- Produces: `carica_storico(percorso: str) -> list[str]`
- Produces: `salva_storico(percorso: str, impronte: list[str]) -> None`
- Produces: `registra_invio(percorso: str, storico: list[str], impronta: str) -> list[str]`
- Produces: constants `MAX_STORICO = 7`, `VERSIONE_STORICO = 1`, `PERCORSO_STORICO`

- [ ] **Step 1: Scrivere i test fallenti dello storico**

Creare `tests/test_whatsapp_bot.py` con:

```python
import json
import os
import tempfile
import unittest

from whatsapp_bot import carica_storico, registra_invio, salva_storico


class StoricoInviiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.percorso = os.path.join(self.directory.name, "storico_invii.json")

    def tearDown(self):
        self.directory.cleanup()

    def test_file_assente_restituisce_lista_vuota(self):
        self.assertEqual([], carica_storico(self.percorso))

    def test_salvataggio_e_caricamento_mantengono_le_impronte(self):
        impronte = [f"{indice:064x}" for indice in range(3)]
        salva_storico(self.percorso, impronte)
        self.assertEqual(impronte, carica_storico(self.percorso))

    def test_registrazione_mantiene_solo_gli_ultimi_sette(self):
        storico = [f"{indice:064x}" for indice in range(7)]
        nuova = f"{99:064x}"
        aggiornato = registra_invio(self.percorso, storico, nuova)
        self.assertEqual(storico[1:] + [nuova], aggiornato)
        self.assertEqual(aggiornato, carica_storico(self.percorso))

    def test_json_non_valido_non_viene_azzerato(self):
        with open(self.percorso, "w", encoding="utf-8") as file:
            file.write("non-json")
        with self.assertRaisesRegex(ValueError, "storico degli invii non valido"):
            carica_storico(self.percorso)

    def test_hash_non_valido_viene_rifiutato(self):
        with self.assertRaisesRegex(ValueError, "impronta SHA-256 non valida"):
            salva_storico(self.percorso, ["abc"])
```

- [ ] **Step 2: Eseguire i test e verificare il fallimento**

Run: `python -m unittest discover -s tests -p "test_*.py" -v`

Expected: `ImportError` perché `carica_storico`, `salva_storico` e `registra_invio` non esistono.

- [ ] **Step 3: Implementare lo storico con scrittura atomica**

In `whatsapp_bot.py`, aggiungere `json` e definire:

```python
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PERCORSO_PROFILO = os.path.join(BASE_DIR, "ProfiloChrome")
PERCORSO_STORICO = os.path.join(BASE_DIR, "storico_invii.json")
VERSIONE_STORICO = 1
MAX_STORICO = 7


def _valida_impronte(impronte):
    if not isinstance(impronte, list) or len(impronte) > MAX_STORICO:
        raise ValueError("Lo storico degli invii non valido: dimensione non ammessa.")
    for impronta in impronte:
        if (
            not isinstance(impronta, str)
            or len(impronta) != 64
            or any(carattere not in "0123456789abcdef" for carattere in impronta)
        ):
            raise ValueError("Impronta SHA-256 non valida nello storico.")


def carica_storico(percorso):
    try:
        with open(percorso, "r", encoding="utf-8") as file:
            dati = json.load(file)
    except FileNotFoundError:
        return []
    except (json.JSONDecodeError, OSError) as errore:
        raise ValueError("Lo storico degli invii non valido o non leggibile.") from errore

    if not isinstance(dati, dict) or dati.get("versione") != VERSIONE_STORICO:
        raise ValueError("Lo storico degli invii non valido: versione non supportata.")
    impronte = dati.get("ultime_impronte")
    _valida_impronte(impronte)
    return list(impronte)


def salva_storico(percorso, impronte):
    _valida_impronte(impronte)
    percorso_temporaneo = f"{percorso}.tmp"
    try:
        with open(percorso_temporaneo, "w", encoding="utf-8") as file:
            json.dump(
                {"versione": VERSIONE_STORICO, "ultime_impronte": impronte},
                file,
                ensure_ascii=False,
                indent=2,
            )
            file.flush()
            os.fsync(file.fileno())
        os.replace(percorso_temporaneo, percorso)
    finally:
        if os.path.exists(percorso_temporaneo):
            os.remove(percorso_temporaneo)


def registra_invio(percorso, storico, impronta):
    aggiornato = (list(storico) + [impronta])[-MAX_STORICO:]
    salva_storico(percorso, aggiornato)
    return aggiornato
```

Aggiungere alla fine di `.gitignore`:

```gitignore
# Stato locale del bot WhatsApp
storico_invii.json
storico_invii.json.tmp
```

- [ ] **Step 4: Eseguire i test dello storico**

Run: `python -m unittest discover -s tests -p "test_*.py" -v`

Expected: 5 test `OK`.

- [ ] **Step 5: Committare lo storico**

```powershell
git add -- .gitignore whatsapp_bot.py tests/test_whatsapp_bot.py
git commit -m "feat: persist recent image fingerprints"
```

---

### Task 2: Impronta del contenuto e scelta casuale

**Files:**
- Modify: `whatsapp_bot.py`
- Modify: `tests/test_whatsapp_bot.py`

**Interfaces:**
- Consumes: `carica_storico(percorso: str) -> list[str]`
- Produces: `CandidatoImmagine(messaggio, immagine, impronta)`
- Produces: `calcola_impronta_immagine(driver, immagine) -> str`
- Produces: `scegli_candidato(candidati, storico, scelta=random.choice) -> CandidatoImmagine | None`

- [ ] **Step 1: Aggiungere i test fallenti per duplicati e casualità controllata**

In `tests/test_whatsapp_bot.py`, aggiungere:

```python
from whatsapp_bot import CandidatoImmagine, scegli_candidato


class SceltaImmagineTests(unittest.TestCase):
    def test_esclude_hash_presenti_nello_storico_e_duplicati_correnti(self):
        gia_inviata = "a" * 64
        nuova = "b" * 64
        candidati = [
            CandidatoImmagine("m1", "i1", gia_inviata),
            CandidatoImmagine("m2", "i2", nuova),
            CandidatoImmagine("m3", "i3", nuova),
        ]
        ricevuti = []

        def prima_opzione(opzioni):
            ricevuti.extend(opzioni)
            return opzioni[0]

        scelto = scegli_candidato(candidati, [gia_inviata], prima_opzione)
        self.assertEqual(nuova, scelto.impronta)
        self.assertEqual(1, len(ricevuti))

    def test_restituisce_none_quando_tutti_i_contenuti_sono_recenti(self):
        impronta = "c" * 64
        candidati = [CandidatoImmagine("m1", "i1", impronta)]
        self.assertIsNone(scegli_candidato(candidati, [impronta]))
```

- [ ] **Step 2: Eseguire i test e verificare il fallimento**

Run: `python -m unittest discover -s tests -p "test_*.py" -v`

Expected: `ImportError` per `CandidatoImmagine` e `scegli_candidato`.

- [ ] **Step 3: Implementare modello, hash browser e selezione**

In `whatsapp_bot.py`, aggiungere:

```python
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class CandidatoImmagine:
    messaggio: object
    immagine: object
    impronta: str


def calcola_impronta_immagine(driver, immagine):
    risultato = driver.execute_async_script(
        """
        const immagine = arguments[0];
        const completa = arguments[arguments.length - 1];
        (async () => {
            const url = immagine.currentSrc || immagine.src;
            const risposta = await fetch(url);
            if (!risposta.ok) throw new Error(`HTTP ${risposta.status}`);
            const contenuto = await risposta.arrayBuffer();
            const digest = await crypto.subtle.digest('SHA-256', contenuto);
            const impronta = Array.from(new Uint8Array(digest))
                .map(byte => byte.toString(16).padStart(2, '0'))
                .join('');
            completa({ok: true, impronta});
        })().catch(errore => completa({ok: false, errore: String(errore)}));
        """,
        immagine,
    )
    if not risultato or not risultato.get("ok"):
        dettaglio = (risultato or {}).get("errore", "risposta assente")
        raise RuntimeError(f"Impossibile leggere l'immagine: {dettaglio}")
    impronta = risultato.get("impronta", "")
    _valida_impronte([impronta])
    return impronta


def scegli_candidato(candidati, storico, scelta=random.choice):
    recenti = set(storico)
    impronte_viste = set()
    idonei = []
    for candidato in candidati:
        if candidato.impronta in recenti or candidato.impronta in impronte_viste:
            continue
        impronte_viste.add(candidato.impronta)
        idonei.append(candidato)
    return scelta(idonei) if idonei else None
```

Impostare `driver.set_script_timeout(15)` in `configura_browser()` dopo la creazione del driver.

- [ ] **Step 4: Eseguire tutti i test**

Run: `python -m unittest discover -s tests -p "test_*.py" -v`

Expected: 7 test `OK`.

- [ ] **Step 5: Committare impronta e selezione**

```powershell
git add -- whatsapp_bot.py tests/test_whatsapp_bot.py
git commit -m "feat: select images by content fingerprint"
```

---

### Task 3: Scansione dei messaggi e scorrimento limitato

**Files:**
- Modify: `whatsapp_bot.py`
- Modify: `tests/test_whatsapp_bot.py`

**Interfaces:**
- Consumes: `calcola_impronta_immagine(driver, immagine) -> str`
- Consumes: `scegli_candidato(candidati, storico, scelta) -> CandidatoImmagine | None`
- Produces: `trova_immagini_nei_messaggi(driver) -> list[tuple[object, object]]`
- Produces: `raccogli_candidati(driver, storico, max_scorrimenti=20) -> list[CandidatoImmagine]`

- [ ] **Step 1: Scrivere test fallenti per filtro immagini e limite di scorrimento**

Aggiungere a `tests/test_whatsapp_bot.py` fake minimali con `find_elements`, `get_attribute`, `is_displayed` ed `execute_script`. Verificare questi casi con codice esplicito:

```python
from unittest.mock import Mock, patch

from whatsapp_bot import raccogli_candidati


class RaccoltaCandidatiTests(unittest.TestCase):
    @patch("whatsapp_bot.calcola_impronta_immagine", return_value="d" * 64)
    @patch("whatsapp_bot.trova_immagini_nei_messaggi")
    def test_ritorna_il_candidato_senza_scorrere_se_idoneo(
        self, trova_immagini, calcola_impronta
    ):
        messaggio = Mock()
        immagine = Mock()
        trova_immagini.return_value = [(messaggio, immagine)]
        candidati = raccogli_candidati(Mock(), [], max_scorrimenti=20)
        self.assertEqual(["d" * 64], [candidato.impronta for candidato in candidati])
        calcola_impronta.assert_called_once()

    @patch("whatsapp_bot.scorri_cronologia_verso_alto", return_value=False)
    @patch("whatsapp_bot.trova_immagini_nei_messaggi", return_value=[])
    def test_interrompe_la_ricerca_se_non_puo_scorrere(
        self, trova_immagini, scorri
    ):
        self.assertEqual([], raccogli_candidati(Mock(), [], max_scorrimenti=20))
        scorri.assert_called_once()
```

- [ ] **Step 2: Eseguire i test e verificare il fallimento**

Run: `python -m unittest discover -s tests -p "test_*.py" -v`

Expected: `ImportError` per `raccogli_candidati`.

- [ ] **Step 3: Implementare scansione, filtro e scorrimento**

Usare selettori centralizzati:

```python
from selenium.common.exceptions import TimeoutException

MAX_SCORRIMENTI = 20
SELETTORE_RIGHE_MESSAGGIO = (
    '//div[@role="row"][.//div[@data-pre-plain-text] and .//img]'
)


def trova_immagini_nei_messaggi(driver):
    risultati = []
    for messaggio in driver.find_elements(By.XPATH, SELETTORE_RIGHE_MESSAGGIO):
        for immagine in messaggio.find_elements(By.XPATH, ".//img"):
            if not immagine.is_displayed():
                continue
            alt = (immagine.get_attribute("alt") or "").casefold()
            larghezza, altezza = driver.execute_script(
                "return [arguments[0].naturalWidth, arguments[0].naturalHeight];",
                immagine,
            )
            if "sticker" in alt or min(larghezza or 0, altezza or 0) < 120:
                continue
            risultati.append((messaggio, immagine))
    return risultati


def scorri_cronologia_verso_alto(driver):
    righe = driver.find_elements(By.XPATH, '//div[@role="row"][.//div[@data-pre-plain-text]]')
    if not righe:
        return False
    stato_precedente = (righe[0].id, len(righe))
    spostato = driver.execute_script(
        """
        let elemento = arguments[0];
        while (elemento && elemento.scrollHeight <= elemento.clientHeight) {
            elemento = elemento.parentElement;
        }
        if (!elemento) return false;
        const prima = elemento.scrollTop;
        elemento.scrollTop = Math.max(0, prima - elemento.clientHeight * 0.8);
        return elemento.scrollTop !== prima;
        """,
        righe[0],
    )
    if not spostato:
        return False

    def cronologia_cambiata(current_driver):
        righe_correnti = current_driver.find_elements(
            By.XPATH, '//div[@role="row"][.//div[@data-pre-plain-text]]'
        )
        if not righe_correnti:
            return False
        return (righe_correnti[0].id, len(righe_correnti)) != stato_precedente

    try:
        WebDriverWait(driver, 5).until(cronologia_cambiata)
    except TimeoutException:
        return False
    return True


def raccogli_candidati(driver, storico, max_scorrimenti=MAX_SCORRIMENTI):
    for _ in range(max_scorrimenti + 1):
        candidati = []
        for messaggio, immagine in trova_immagini_nei_messaggi(driver):
            try:
                impronta = calcola_impronta_immagine(driver, immagine)
            except RuntimeError as errore:
                print(f"Immagine ignorata: {errore}")
                continue
            candidati.append(CandidatoImmagine(messaggio, immagine, impronta))
        if scegli_candidato(candidati, storico) is not None:
            return candidati
        if not scorri_cronologia_verso_alto(driver):
            break
    return []
```

Non inserire `sleep`: l'attesa sopra controlla la comparsa di nuove righe tramite `WebDriverWait`.

- [ ] **Step 4: Eseguire tutti i test**

Run: `python -m unittest discover -s tests -p "test_*.py" -v`

Expected: 9 test `OK`.

- [ ] **Step 5: Committare la scansione**

```powershell
git add -- whatsapp_bot.py tests/test_whatsapp_bot.py
git commit -m "feat: scan eligible WhatsApp images"
```

---

### Task 4: Inoltro del messaggio selezionato e conferma UI

**Files:**
- Modify: `whatsapp_bot.py:130-180`
- Modify: `tests/test_whatsapp_bot.py`

**Interfaces:**
- Replaces: `inoltra_ultimo_messaggio(driver, destinazione)`
- Produces: `inoltra_messaggio(driver, messaggio, destinazione) -> bool`
- Guarantee: restituisce `True` soltanto dopo la scomparsa del pannello di inoltro.

- [ ] **Step 1: Scrivere il test fallente del contratto booleano**

Separare la decisione di registrazione dalla UI mediante una funzione orchestratrice testabile:

```python
from unittest.mock import patch

from whatsapp_bot import CandidatoImmagine, esegui_invio_immagine


class OrchestrazioneInvioTests(unittest.TestCase):
    @patch("whatsapp_bot.registra_invio")
    @patch("whatsapp_bot.inoltra_messaggio", return_value=False)
    @patch("whatsapp_bot.raccogli_candidati")
    def test_non_registra_se_inoltro_non_confermato(
        self, raccogli, inoltra, registra
    ):
        candidato = CandidatoImmagine("messaggio", "immagine", "e" * 64)
        raccogli.return_value = [candidato]
        esito = esegui_invio_immagine(Mock(), "Destinazione", [], "storico.json")
        self.assertFalse(esito)
        registra.assert_not_called()
```

- [ ] **Step 2: Eseguire il test e verificare il fallimento**

Run: `python -m unittest discover -s tests -p "test_*.py" -v`

Expected: `ImportError` per `inoltra_messaggio` ed `esegui_invio_immagine`.

- [ ] **Step 3: Sostituire l'inoltro dell'ultimo messaggio**

Implementare `inoltra_messaggio` usando il `messaggio` ricevuto, `ActionChains`, attese esplicite e selezione esatta della destinazione. La parte finale deve conservare un riferimento al pannello o al pulsante di invio e attendere:

```python
def inoltra_messaggio(driver, messaggio, destinazione):
    webdriver.ActionChains(driver).move_to_element(messaggio).perform()
    menu = WebDriverWait(messaggio, 10).until(
        lambda elemento: elemento.find_element(
            By.XPATH, './/span[@data-icon="down-context"]'
        )
    )
    menu.click()
    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (By.XPATH, '//div[@aria-label="Inoltra" or @aria-label="Forward message"]')
        )
    ).click()
    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, '//span[@data-icon="forward"]'))
    ).click()

    ricerca_destinazione = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (By.XPATH, '//*[@role="textbox" and (@data-tab="6" or @contenteditable)]')
        )
    )
    ricerca_destinazione.send_keys(destinazione)
    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (By.XPATH, f'//span[@title="{destinazione}"]')
        )
    ).click()
    pulsante_invio = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, '//span[@data-icon="send"]'))
    )
    pulsante_invio.click()
    WebDriverWait(driver, 15).until(EC.staleness_of(pulsante_invio))
    return True
```

Se uno dei controlli non è disponibile, lasciare propagare l'eccezione Selenium all'orchestratore; non restituire successo.

- [ ] **Step 4: Implementare l'orchestrazione senza aggiornamenti anticipati**

```python
def esegui_invio_immagine(driver, destinazione, storico, percorso_storico):
    candidati = raccogli_candidati(driver, storico)
    candidato = scegli_candidato(candidati, storico)
    if candidato is None:
        print("Nessuna immagine idonea trovata: nessun invio eseguito.")
        return False
    if not inoltra_messaggio(driver, candidato.messaggio, destinazione):
        return False
    registra_invio(percorso_storico, storico, candidato.impronta)
    return True
```

- [ ] **Step 5: Aggiungere e passare il test del percorso riuscito**

```python
    @patch("whatsapp_bot.registra_invio")
    @patch("whatsapp_bot.inoltra_messaggio", return_value=True)
    @patch("whatsapp_bot.raccogli_candidati")
    def test_registra_solo_dopo_inoltro_confermato(
        self, raccogli, inoltra, registra
    ):
        candidato = CandidatoImmagine("messaggio", "immagine", "f" * 64)
        raccogli.return_value = [candidato]
        esito = esegui_invio_immagine(Mock(), "Destinazione", [], "storico.json")
        self.assertTrue(esito)
        registra.assert_called_once_with("storico.json", [], "f" * 64)
```

Run: `python -m unittest discover -s tests -p "test_*.py" -v`

Expected: 11 test `OK`.

- [ ] **Step 6: Committare inoltro e orchestrazione**

```powershell
git add -- whatsapp_bot.py tests/test_whatsapp_bot.py
git commit -m "feat: forward selected image safely"
```

---

### Task 5: Integrazione nel main e verifiche finali

**Files:**
- Modify: `whatsapp_bot.py:183-205`
- Verify: `avvia_bot.bat`
- Test: `tests/test_whatsapp_bot.py`

**Interfaces:**
- Consumes: `carica_storico`, `esegui_invio_immagine`, `PERCORSO_STORICO`
- Produces: una esecuzione batch con al massimo un invio e messaggio terminale verificabile.

- [ ] **Step 1: Rendere la chiusura del browser garantita**

Riscrivere `main()` con `try/finally` e messaggio di successo soltanto sul valore `True`:

```python
def main():
    driver = None
    try:
        storico = carica_storico(PERCORSO_STORICO)
        driver = configura_browser()
        driver.get("https://whatsapp.com")
        accedi_a_whatsapp_web(driver)
        print("Attesa del caricamento di WhatsApp Web...")

        if not cerca_e_seleziona_chat(driver, GRUPPO_SORGENTE):
            return

        if esegui_invio_immagine(
            driver,
            GRUPPO_DESTINAZIONE,
            storico,
            PERCORSO_STORICO,
        ):
            print(
                f"Invio eseguito: una nuova immagine da '{GRUPPO_SORGENTE}' "
                f"è stata inviata a '{GRUPPO_DESTINAZIONE}'."
            )
    except (RuntimeError, ValueError, WebDriverException) as errore:
        print(f"Invio non eseguito: {errore}")
    finally:
        if driver is not None:
            print("Chiusura del browser tra 5 secondi...")
            time.sleep(5)
            driver.quit()
```

Aggiungere `WebDriverException` agli import Selenium:

```python
from selenium.common.exceptions import WebDriverException
```

- [ ] **Step 2: Eseguire test e controllo sintattico**

Run: `python -m unittest discover -s tests -p "test_*.py" -v`

Expected: 11 test `OK`.

Run: `python -m py_compile whatsapp_bot.py tests/test_whatsapp_bot.py`

Expected: exit code `0`, nessun output.

- [ ] **Step 3: Controllare diff e dati esclusi**

```powershell
git diff --check
git status --short
git check-ignore -v storico_invii.json
```

Expected: nessun errore di whitespace; `storico_invii.json` risulta ignorato; nessun file sotto `ProfiloChrome/` viene aggiunto allo staging.

- [ ] **Step 4: Committare l'integrazione**

```powershell
git add -- whatsapp_bot.py tests/test_whatsapp_bot.py .gitignore
git commit -m "feat: automate non-repeating image delivery"
```

- [ ] **Step 5: Richiedere conferma immediata prima del test reale**

Prima di avviare `avvia_bot.bat`, chiedere esplicitamente all'utente l'autorizzazione a inoltrare una immagine reale da `Rosario` a `Destinazione`. Non eseguire il comando senza quella conferma.

- [ ] **Step 6: Eseguire il test manuale controllato dopo conferma**

Run dalla root del progetto: `cmd /c avvia_bot.bat`

Verificare visivamente e nel terminale:

```text
Invio eseguito: una nuova immagine da 'Rosario' è stata inviata a 'Destinazione'.
```

Controllare inoltre che `storico_invii.json` contenga una sola nuova impronta al primo invio, che un secondo invio non riutilizzi la stessa impronta e che il terminale resti aperto sul `pause` del batch.
