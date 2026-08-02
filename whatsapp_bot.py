import json
import msvcrt
import os
import random
import tempfile
import time
from dataclasses import dataclass
from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# --- CONFIGURAZIONE ---
# Inserisci i nomi ESATTI come appaiono nella tua lista chat di WhatsApp
GRUPPO_SORGENTE = "Rosario"
GRUPPO_DESTINAZIONE = "Destinazione"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PERCORSO_PROFILO = os.path.join(BASE_DIR, "ProfiloChrome")
PERCORSO_STORICO = os.path.join(BASE_DIR, "storico_invii.json")
PERCORSO_LOCK = os.path.join(BASE_DIR, ".whatsapp_bot.lock")
VERSIONE_STORICO = 1
MAX_STORICO = 7
MAX_SCORRIMENTI = 20


class ErroreSalvataggioStorico(RuntimeError):
    """Segnala che un inoltro confermato non ha aggiornato lo storico locale."""


class ErroreIstanzaGiaInEsecuzione(RuntimeError):
    """Segnala che un'altra istanza del bot possiede già il lock esclusivo."""


# WhatsApp Web cambia spesso struttura interna: la ricerca e identificata
# dall'etichetta accessibile, non dall'ordine o da attributi temporanei.
SELETTORE_CANDIDATI_RICERCA = (
    '//*[@role="textbox" or @contenteditable="true" or self::input]'
)
SELETTORE_ACCESSO = (
    '//*[self::a or self::button]['
    'normalize-space()="Accedi" or normalize-space()="Log in" '
    'or .//*[normalize-space()="Accedi" or normalize-space()="Log in"]]'
)
SELETTORE_RIGHE_MESSAGGIO = (
    '//div[@role="row"][.//div[@data-pre-plain-text] and .//img]'
)
SELETTORE_RIGHE_CRONOLOGIA = '//div[@role="row"][.//div[@data-pre-plain-text]]'
SELETTORE_MENU_CONTESTO_MESSAGGIO = './/span[@data-icon="down-context"]'
SELETTORE_MENU_CONTESTO_VISIBILE = (
    '//*[self::button or @role="button"]['
    '@aria-label="Menu contestuale" or @aria-label="Context menu" or '
    './/span[@data-icon="down-context" or @data-icon="chevron-down"]]'
    ' | //span[@data-icon="down-context" or @data-icon="chevron-down"]'
)
SELETTORE_AZIONE_INOLTRO = (
    '//*[(@role="button" or @role="menuitem" or '
    '(self::div and @tabindex="0")) and ('
    '@aria-label="Inoltra" or @aria-label="Forward message" or '
    '@aria-label="Forward" or normalize-space(.)="Inoltra" or '
    'normalize-space(.)="Forward")]'
)
SELETTORE_CONFERMA_INOLTRO = '//span[@data-icon="forward"]'
SELETTORE_DIALOG_INOLTRO = (
    '//*[@role="dialog" and '
    './/*[@role="textbox" and @contenteditable="true"]]'
)
SELETTORE_RICERCA_DESTINAZIONE = (
    './/*[@role="textbox" and @contenteditable="true"]'
)
SELETTORE_PULSANTE_INVIO = './/span[@data-icon="send"]'


def crea_literal_xpath(valore):
    if "'" not in valore:
        return f"'{valore}'"
    if '"' not in valore:
        return f'"{valore}"'
    parti = valore.split("'")
    return "concat(" + ', "\'", '.join(f"'{parte}'" for parte in parti) + ")"


def crea_selettore_destinazione(destinazione):
    # XPath non offre un carattere di escape: il literal deve scegliere o comporre
    # il delimitatore per mantenere la selezione esatta dei nomi chat validi.
    return f".//span[@title={crea_literal_xpath(destinazione)}]"


@dataclass(frozen=True)
class CandidatoImmagine:
    messaggio: object
    immagine: object
    impronta: str


def _valida_impronte(impronte):
    if not isinstance(impronte, list) or len(impronte) > MAX_STORICO:
        raise ValueError("Lo storico degli invii non valido: dimensione non ammessa.")
    for impronta in impronte:
        if (
            not isinstance(impronta, str)
            or len(impronta) != 64
            or any(carattere not in "0123456789abcdef" for carattere in impronta)
        ):
            raise ValueError("impronta SHA-256 non valida nello storico.")


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
    percorso_temporaneo = None
    errore_salvataggio = None
    try:
        directory = os.path.dirname(os.path.abspath(percorso))
        prefisso = f".{os.path.basename(percorso)}."
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=directory,
            prefix=prefisso,
            suffix=".tmp",
            delete=False,
        ) as file:
            percorso_temporaneo = file.name
            json.dump(
                {"versione": VERSIONE_STORICO, "ultime_impronte": impronte},
                file,
                ensure_ascii=False,
                indent=2,
            )
            file.flush()
            os.fsync(file.fileno())
        os.replace(percorso_temporaneo, percorso)
    except OSError as errore:
        errore_salvataggio = errore
    finally:
        try:
            if percorso_temporaneo and os.path.exists(percorso_temporaneo):
                os.remove(percorso_temporaneo)
        except OSError as errore:
            if errore_salvataggio is None:
                errore_salvataggio = errore

    if errore_salvataggio is not None:
        raise ErroreSalvataggioStorico(
            "Impossibile salvare lo storico degli invii."
        ) from errore_salvataggio


def registra_invio(percorso, storico, impronta):
    aggiornato = (list(storico) + [impronta])[-MAX_STORICO:]
    salva_storico(percorso, aggiornato)
    return aggiornato


def acquisisci_lock_istanza(percorso):
    try:
        file_lock = open(percorso, "a+b")
        file_lock.seek(0, os.SEEK_END)
        if file_lock.tell() == 0:
            file_lock.write(b"\0")
            file_lock.flush()
        file_lock.seek(0)
    except OSError as errore:
        if "file_lock" in locals():
            file_lock.close()
        raise RuntimeError(
            "Impossibile predisporre il lock di esecuzione del bot."
        ) from errore

    try:
        msvcrt.locking(file_lock.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError as errore:
        file_lock.close()
        raise ErroreIstanzaGiaInEsecuzione(
            "Il bot è già in esecuzione. Attendi la chiusura dell'altra istanza."
        ) from errore
    return file_lock


def rilascia_lock_istanza(file_lock):
    try:
        file_lock.seek(0)
        msvcrt.locking(file_lock.fileno(), msvcrt.LK_UNLCK, 1)
    finally:
        file_lock.close()


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


def trova_immagini_nei_messaggi(driver):
    risultati = []
    righe_messaggio = driver.find_elements(By.XPATH, SELETTORE_RIGHE_MESSAGGIO)
    immagini_nascoste = 0
    sticker = 0
    immagini_piccole = 0

    for messaggio in righe_messaggio:
        try:
            immagini = messaggio.find_elements(By.XPATH, ".//img")
        except (StaleElementReferenceException, TimeoutException) as errore:
            print(f"Messaggio ignorato durante la scansione: {errore}")
            continue

        for immagine in immagini:
            try:
                if not immagine.is_displayed():
                    immagini_nascoste += 1
                    continue
                alt = (immagine.get_attribute("alt") or "").casefold()
                larghezza, altezza = driver.execute_script(
                    "return [arguments[0].naturalWidth, arguments[0].naturalHeight];",
                    immagine,
                )
                if "sticker" in alt:
                    sticker += 1
                    continue
                if min(larghezza or 0, altezza or 0) < 120:
                    immagini_piccole += 1
                    continue
            except (StaleElementReferenceException, TimeoutException) as errore:
                print(f"Immagine ignorata durante la scansione: {errore}")
                continue
            risultati.append((messaggio, immagine))
    print(
        "Scansione immagini: "
        f"{len(righe_messaggio)} righe, {len(risultati)} idonee, "
        f"{immagini_nascoste} nascoste, {sticker} sticker, "
        f"{immagini_piccole} troppo piccole."
    )
    return risultati


def trova_contenitore_scroll(driver, elemento, max_antenati=15):
    for _ in range(max_antenati):
        metriche = driver.execute_script(
            """
            const elemento = arguments[0];
            const stile = window.getComputedStyle(elemento);
            return {
                scorrevole:
                    ['auto', 'scroll', 'overlay'].includes(stile.overflowY) &&
                    elemento.scrollHeight > elemento.clientHeight
            };
            """,
            elemento,
        )
        if metriche.get("scorrevole"):
            return elemento
        try:
            elemento = elemento.find_element(By.XPATH, "..")
        except NoSuchElementException:
            return None
    return None


def scorri_cronologia_verso_alto(driver, direzione=-1):
    for tentativo in range(3):
        try:
            righe = driver.find_elements(By.XPATH, SELETTORE_RIGHE_CRONOLOGIA)
            if not righe:
                print("Scorrimento interrotto: nessuna riga messaggio trovata.")
                return False
            stato_precedente = (righe[0].id, len(righe))
            contenitore_scroll = trova_contenitore_scroll(driver, righe[0])
            if contenitore_scroll is None:
                print(
                    "Scorrimento interrotto: contenitore verticale "
                    "scorrevole non trovato."
                )
                return False
            spostato = driver.execute_script(
                """
                let elemento = arguments[0];
                const direzione = arguments[1];
                const prima = elemento.scrollTop;
                elemento.scrollTop =
                    prima + direzione * elemento.clientHeight * 0.8;
                return elemento.scrollTop !== prima;
                """,
                contenitore_scroll,
                direzione,
            )
            break
        except StaleElementReferenceException:
            if tentativo == 2:
                print(
                    "Scorrimento interrotto: WhatsApp ha aggiornato "
                    "ripetutamente la cronologia."
                )
                return False
    if not spostato:
        print("Scorrimento interrotto: la cronologia non può salire ulteriormente.")
        return False

    def cronologia_cambiata(current_driver):
        righe_correnti = current_driver.find_elements(
            By.XPATH, SELETTORE_RIGHE_CRONOLOGIA
        )
        if not righe_correnti:
            return False
        try:
            return (righe_correnti[0].id, len(righe_correnti)) != stato_precedente
        except StaleElementReferenceException:
            return False

    try:
        WebDriverWait(driver, 5).until(cronologia_cambiata)
    except TimeoutException:
        print("Scorrimento interrotto: la cronologia non è cambiata entro 5 secondi.")
        return False
    return True


def raccogli_candidati(driver, storico, max_scorrimenti=MAX_SCORRIMENTI):
    direzione_scroll = -1
    scorrimenti_eseguiti = 0
    for indice_scansione in range(max_scorrimenti + 1):
        candidati = []
        for messaggio, immagine in trova_immagini_nei_messaggi(driver):
            try:
                impronta = calcola_impronta_immagine(driver, immagine)
            except (
                RuntimeError,
                StaleElementReferenceException,
                TimeoutException,
            ) as errore:
                print(f"Immagine ignorata: {errore}")
                continue
            candidati.append(CandidatoImmagine(messaggio, immagine, impronta))
        print(
            f"Scansione {indice_scansione + 1}/{max_scorrimenti + 1}: "
            f"{len(candidati)} immagini leggibili."
        )
        if scegli_candidato(candidati, storico) is not None:
            return candidati
        if indice_scansione == max_scorrimenti:
            break
        if not scorri_cronologia_verso_alto(driver, direzione_scroll):
            if scorrimenti_eseguiti > 0 or direzione_scroll == 1:
                break
            direzione_scroll = 1
            print("Prima direzione bloccata: provo la direzione opposta.")
            if not scorri_cronologia_verso_alto(driver, direzione_scroll):
                break
        scorrimenti_eseguiti += 1
    return []


def configura_browser():
    options = Options()
    # Utilizza una cartella dati personalizzata per salvare il login di WhatsApp
    options.add_argument(f"--user-data-dir={PERCORSO_PROFILO}")
    options.add_argument("--profile-directory=Default")
    options.add_argument("--start-maximized")
    # Evita il rilevamento automatizzato basilare
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_script_timeout(15)
    return driver


def accedi_a_whatsapp_web(driver):
    print("Apertura di WhatsApp Web...")
    finestre_iniziali = set(driver.window_handles)
    pulsante_accesso = WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable((By.XPATH, SELETTORE_ACCESSO))
    )
    pulsante_accesso.click()

    WebDriverWait(driver, 20).until(
        lambda current_driver: (
            len(current_driver.window_handles) > len(finestre_iniziali)
            or "web.whatsapp.com" in current_driver.current_url
        )
    )

    nuove_finestre = set(driver.window_handles) - finestre_iniziali
    if nuove_finestre:
        driver.switch_to.window(nuove_finestre.pop())


def trova_campo_ricerca_visibile(driver):
    for elemento in driver.find_elements(By.XPATH, SELETTORE_CANDIDATI_RICERCA):
        try:
            attributi = {
                "aria-label": elemento.get_attribute("aria-label"),
                "aria-placeholder": elemento.get_attribute("aria-placeholder"),
                "placeholder": elemento.get_attribute("placeholder"),
                "data-placeholder": elemento.get_attribute("data-placeholder"),
                "data-tab": elemento.get_attribute("data-tab"),
            }
            descrizione = " ".join(
                valore for valore in attributi.values() if valore
            ).casefold()
            identificato_come_ricerca = (
                "cerca" in descrizione
                or "search" in descrizione
                or attributi["data-tab"] == "3"
            )

            if (
                elemento.is_displayed()
                and elemento.is_enabled()
                and identificato_come_ricerca
            ):
                attributi_presenti = {
                    nome: valore for nome, valore in attributi.items() if valore
                }
                print(
                    "Campo di ricerca individuato: "
                    f"tag={elemento.tag_name}, attributi={attributi_presenti}"
                )
                return elemento
        except StaleElementReferenceException:
            continue

    return False


def cerca_e_seleziona_chat(driver, nome_chat):
    print("Attesa del caricamento della lista chat...")
    try:
        # L'attesa copre anche un eventuale accesso tramite codice QR.
        search_box = WebDriverWait(driver, 120).until(trova_campo_ricerca_visibile)
        print(f"Ricerca della chat: {nome_chat}...")
        search_box.click()
        search_box.send_keys(Keys.CONTROL, "a")
        search_box.send_keys(Keys.BACKSPACE)
        search_box.send_keys(nome_chat)

        # Seleziona il risultato dal titolo esatto, anziche' assumere che
        # il primo risultato o il tasto Invio corrispondano alla chat richiesta.
        chat_sorgente = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable(
                (By.XPATH, f'//span[@title="{nome_chat}"]')
            )
        )
        chat_sorgente.click()
        print(f"Chat sorgente '{nome_chat}' selezionata.")
        return True
    except Exception as e:
        print(f"Errore nella ricerca della chat: {e}")
        return False


def attendi_fase_inoltro(radice, timeout, condizione, fase):
    try:
        return WebDriverWait(radice, timeout).until(condizione)
    except TimeoutException as errore:
        raise RuntimeError(f"Timeout durante {fase}.") from errore


def trova_menu_contestuale_visibile(driver):
    for elemento in driver.find_elements(By.XPATH, SELETTORE_MENU_CONTESTO_VISIBILE):
        try:
            if elemento.is_displayed() and elemento.is_enabled():
                return elemento
        except StaleElementReferenceException:
            continue
    return None


def inoltra_messaggio(driver, messaggio, destinazione):
    webdriver.ActionChains(driver).move_to_element(messaggio).perform()
    menu_disponibili = messaggio.find_elements(
        By.XPATH,
        SELETTORE_MENU_CONTESTO_MESSAGGIO,
    )
    if menu_disponibili:
        menu = attendi_fase_inoltro(
            messaggio,
            10,
            EC.element_to_be_clickable(
                (By.XPATH, SELETTORE_MENU_CONTESTO_MESSAGGIO)
            ),
            "l'apertura del menu contestuale del messaggio",
        )
        menu.click()
    else:
        menu_globale = trova_menu_contestuale_visibile(driver)
        if menu_globale is not None:
            menu_globale.click()
        else:
            webdriver.ActionChains(driver).context_click(messaggio).perform()
    attendi_fase_inoltro(
        driver,
        10,
        EC.element_to_be_clickable((By.XPATH, SELETTORE_AZIONE_INOLTRO)),
        "la selezione del comando Inoltra",
    ).click()
    attendi_fase_inoltro(
        driver,
        10,
        EC.element_to_be_clickable((By.XPATH, SELETTORE_CONFERMA_INOLTRO)),
        "la conferma del messaggio da inoltrare",
    ).click()

    dialog_inoltro = attendi_fase_inoltro(
        driver,
        10,
        EC.visibility_of_element_located((By.XPATH, SELETTORE_DIALOG_INOLTRO)),
        "l'apertura del pannello di inoltro",
    )
    ricerca_destinazione = attendi_fase_inoltro(
        dialog_inoltro,
        10,
        EC.element_to_be_clickable((By.XPATH, SELETTORE_RICERCA_DESTINAZIONE)),
        "la ricerca della chat di destinazione",
    )
    ricerca_destinazione.send_keys(destinazione)
    attendi_fase_inoltro(
        dialog_inoltro,
        10,
        EC.element_to_be_clickable(
            (By.XPATH, crea_selettore_destinazione(destinazione))
        ),
        "la selezione della chat di destinazione",
    ).click()
    pulsante_invio = attendi_fase_inoltro(
        dialog_inoltro,
        10,
        EC.element_to_be_clickable((By.XPATH, SELETTORE_PULSANTE_INVIO)),
        "l'attivazione del pulsante di invio",
    )
    pulsante_invio.click()
    attendi_fase_inoltro(
        driver,
        15,
        EC.invisibility_of_element(dialog_inoltro),
        "la conferma conclusiva dell'invio",
    )
    return True


def esegui_invio_immagine(driver, destinazione, storico, percorso_storico):
    candidati = raccogli_candidati(driver, storico)
    candidato = scegli_candidato(candidati, storico)
    if candidato is None:
        print("Nessuna immagine idonea trovata: nessun invio eseguito.")
        return False

    # WhatsApp virtualizza la cronologia e può ricreare i nodi DOM durante
    # il calcolo dell'impronta. Ritrova quindi lo stesso contenuto subito
    # prima dell'interazione, evitando di usare un WebElement ormai stale.
    candidati_aggiornati = raccogli_candidati(driver, storico, max_scorrimenti=0)
    candidato_aggiornato = next(
        (
            corrente
            for corrente in candidati_aggiornati
            if corrente.impronta == candidato.impronta
        ),
        None,
    )
    if candidato_aggiornato is None:
        raise RuntimeError(
            "L'immagine selezionata non è più disponibile nella vista corrente."
        )

    if not inoltra_messaggio(
        driver,
        candidato_aggiornato.messaggio,
        destinazione,
    ):
        return False
    registra_invio(percorso_storico, storico, candidato.impronta)
    return True


def main():
    driver = None
    file_lock = None
    try:
        file_lock = acquisisci_lock_istanza(PERCORSO_LOCK)
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
    except ErroreIstanzaGiaInEsecuzione as errore:
        print(f"Avvio non eseguito: {errore}")
    except ErroreSalvataggioStorico as errore:
        print(
            "Invio eseguito, ma lo storico non è stato salvato. "
            "Non avviare nuovamente il bot finché il problema non è risolto. "
            f"Dettaglio: {errore}"
        )
    except (RuntimeError, ValueError, WebDriverException) as errore:
        print(f"Invio non eseguito: {errore}")
    finally:
        try:
            if driver is not None:
                print("Chiusura del browser tra 5 secondi...")
                time.sleep(5)
                driver.quit()
        finally:
            if file_lock is not None:
                rilascia_lock_istanza(file_lock)


if __name__ == "__main__":
    main()
