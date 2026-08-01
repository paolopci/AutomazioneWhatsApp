import os
import time
from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# --- CONFIGURAZIONE ---
# Inserisci i nomi ESATTI come appaiono nella tua lista chat di WhatsApp
GRUPPO_SORGENTE = "Sorgente"
GRUPPO_DESTINAZIONE = "Destinazione"

# Percorso della cartella del profilo creata al Passo 1
PERCORSO_PROFILO = os.path.join(os.getcwd(), "ProfiloChrome")

# WhatsApp Web cambia spesso struttura interna: la ricerca e identificata
# dall'etichetta accessibile, non dall'ordine o da attributi temporanei.
SELETTORE_CANDIDATI_RICERCA = '//*[@role="textbox" or @contenteditable or self::input]'
SELETTORE_ACCESSO = (
    '//*[self::a or self::button]['
    'normalize-space()="Accedi" or normalize-space()="Log in" '
    'or .//*[normalize-space()="Accedi" or normalize-space()="Log in"]]'
)


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


def inoltra_ultimo_messaggio(driver, destinazione):
    try:
        # Trova tutti i contenitori di messaggi nell'area chat aperta
        messaggi = driver.find_elements(By.XPATH, "//div[@data-pre-plain-text]")
        if not messaggi:
            print("Nessun messaggio trovato nella chat.")
            return

        # Seleziona l'ultimo messaggio (il più recente in basso)
        ultimo_messaggio = messaggi[-1]

        # Muove il mouse virtuale sopra l'ultimo messaggio per far apparire la freccia del menu
        webdriver.ActionChains(driver).move_to_element(ultimo_messaggio).perform()
        time.sleep(1)

        # Clicca sulla frecciatina delle opzioni del messaggio
        menu_button = ultimo_messaggio.find_element(
            By.XPATH, './/span[@data-icon="down-context"]'
        )
        menu_button.click()
        time.sleep(1)

        # Clicca su "Inoltra" (Forward)
        forward_button = driver.find_element(
            By.XPATH, '//div[@aria-label="Inoltra" or @aria-label="Forward message"]'
        )
        forward_button.click()
        time.sleep(1)

        # Clicca sul pulsante di inoltro in basso a destra (l'icona della freccia verso destra)
        confirm_forward = driver.find_element(By.XPATH, '//span[@data-icon="forward"]')
        confirm_forward.click()
        time.sleep(2)

        # Si apre il pannello di ricerca per scegliere a chi inoltrare
        search_dest = driver.find_element(
            By.XPATH, '//div[@contenteditable="true"][@data-tab="6"]'
        )
        search_dest.send_keys(destinazione)
        time.sleep(2)
        search_dest.send_keys(Keys.ENTER)
        time.sleep(1)

        # Clicca sul tasto verde di invio finale
        send_button = driver.find_element(By.XPATH, '//span[@data-icon="send"]')
        send_button.click()
        print(f"Contenuto inoltrato con successo a '{destinazione}'!")
        time.sleep(2)

    except Exception as e:
        print(f"Errore durante la procedura di inoltro: {e}")


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
