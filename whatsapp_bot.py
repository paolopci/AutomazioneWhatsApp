import json
import os
import random
import time
from dataclasses import dataclass
from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
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
VERSIONE_STORICO = 1
MAX_STORICO = 7
MAX_SCORRIMENTI = 20

# WhatsApp Web cambia spesso struttura interna: la ricerca e identificata
# dall'etichetta accessibile, non dall'ordine o da attributi temporanei.
SELETTORE_CANDIDATI_RICERCA = '//*[@role="textbox" or @contenteditable or self::input]'
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
SELETTORE_AZIONE_INOLTRO = (
    '//div[@aria-label="Inoltra" or @aria-label="Forward message"]'
)
SELETTORE_CONFERMA_INOLTRO = '//span[@data-icon="forward"]'
SELETTORE_RICERCA_DESTINAZIONE = (
    '//*[@role="textbox" and (@data-tab="6" or @contenteditable)]'
)
SELETTORE_PULSANTE_INVIO = '//span[@data-icon="send"]'


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
    righe = driver.find_elements(By.XPATH, SELETTORE_RIGHE_CRONOLOGIA)
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
            By.XPATH, SELETTORE_RIGHE_CRONOLOGIA
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
        if _ == max_scorrimenti:
            break
        if not scorri_cronologia_verso_alto(driver):
            break
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


def inoltra_messaggio(driver, messaggio, destinazione):
    webdriver.ActionChains(driver).move_to_element(messaggio).perform()
    menu = WebDriverWait(messaggio, 10).until(
        lambda elemento: elemento.find_element(
            By.XPATH, SELETTORE_MENU_CONTESTO_MESSAGGIO
        )
    )
    menu.click()
    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, SELETTORE_AZIONE_INOLTRO))
    ).click()
    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, SELETTORE_CONFERMA_INOLTRO))
    ).click()

    ricerca_destinazione = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, SELETTORE_RICERCA_DESTINAZIONE))
    )
    ricerca_destinazione.send_keys(destinazione)
    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, f'//span[@title="{destinazione}"]'))
    ).click()
    pulsante_invio = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, SELETTORE_PULSANTE_INVIO))
    )
    pulsante_invio.click()
    WebDriverWait(driver, 15).until(EC.staleness_of(pulsante_invio))
    print(f"Contenuto inoltrato con successo a '{destinazione}'.")
    return True


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


def main():
    driver = configura_browser()
    driver.get("https://whatsapp.com")
    accedi_a_whatsapp_web(driver)

    print(
        "\n[ATTENZIONE] Se è la prima volta, scansiona il codice QR sul browser aperto."
    )
    print("Se hai già fatto l'accesso, attendi il caricamento della pagina.\n")

    # 1. Va nel gruppo sorgente
    if cerca_e_seleziona_chat(driver, GRUPPO_SORGENTE):
        time.sleep(2)
        # 2. Prende l'ultimo elemento (testo o immagine) e lo inoltra al gruppo destinazione
        inoltra_ultimo_messaggio(driver, GRUPPO_DESTINAZIONE)

    print("Procedura completata. Chiusura del browser tra 5 secondi...")
    time.sleep(5)
    driver.quit()


if __name__ == "__main__":
    main()
