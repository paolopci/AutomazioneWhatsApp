import os

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


GRUPPO_SORGENTE = "Rosario"
GRUPPO_DESTINAZIONE = "Destinazione"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PERCORSO_PROFILO = os.path.join(BASE_DIR, "ProfiloChrome")

SELETTORE_RICERCA = '//*[@role="textbox" or @contenteditable="true" or self::input]'
SELETTORE_ACCEDI = (
    '//*[self::a or self::button]['
    'normalize-space()="Accedi" or normalize-space()="Log in"]'
)
SELETTORE_MESSAGGIO_CON_IMMAGINE = (
    '//div[@role="row"][.//div[@data-pre-plain-text] and .//img]'
)
SELETTORE_INOLTRO = (
    '//*[normalize-space(.)="Inoltra" or normalize-space(.)="Forward"]'
)
SELETTORE_CONFERMA_INOLTRO = (
    '//*[@aria-label="Inoltra" or @aria-label="Forward"]'
)
SELETTORE_DIALOG = '//*[@role="dialog"]'
SELETTORE_RICERCA_DESTINAZIONE = (
    './/*[@role="textbox" or @contenteditable="true" or self::input]'
)
SELETTORE_INVIO = '//*[@role="button" and @aria-label="Invia"]'


def configura_browser():
    options = Options()
    options.add_argument(f"--user-data-dir={PERCORSO_PROFILO}")
    options.add_argument("--profile-directory=Default")
    options.add_argument("--start-maximized")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)


def apri_whatsapp_web(driver):
    finestre_iniziali = set(driver.window_handles)
    WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable((By.XPATH, SELETTORE_ACCEDI))
    ).click()
    WebDriverWait(driver, 20).until(
        lambda current_driver: (
            "web.whatsapp.com" in current_driver.current_url
            or len(current_driver.window_handles) > len(finestre_iniziali)
        )
    )
    nuove_finestre = set(driver.window_handles) - finestre_iniziali
    if nuove_finestre:
        driver.switch_to.window(nuove_finestre.pop())


def trova_campo_ricerca(driver):
    def campo_visibile(current_driver):
        for elemento in current_driver.find_elements(By.XPATH, SELETTORE_RICERCA):
            if elemento.is_displayed() and elemento.is_enabled():
                descrizione = " ".join(
                    valore
                    for valore in (
                        elemento.get_attribute("aria-label"),
                        elemento.get_attribute("placeholder"),
                    )
                    if valore
                ).casefold()
                if "cerca" in descrizione or "search" in descrizione:
                    return elemento
        return False

    return WebDriverWait(driver, 30).until(campo_visibile)


def seleziona_chat(driver, nome_chat):
    campo = trova_campo_ricerca(driver)
    campo.click()
    campo.send_keys(Keys.CONTROL, "a")
    campo.send_keys(Keys.BACKSPACE)
    campo.send_keys(nome_chat)
    WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable((By.XPATH, f'//span[@title="{nome_chat}"]'))
    ).click()


def trova_prima_immagine(driver):
    messaggi = WebDriverWait(driver, 20).until(
        lambda current_driver: current_driver.find_elements(
            By.XPATH,
            SELETTORE_MESSAGGIO_CON_IMMAGINE,
        )
    )
    return messaggi[0].find_element(By.XPATH, ".//img")


def inoltra_immagine(driver, messaggio, destinazione):
    fase = "apertura del menu"
    try:
        webdriver.ActionChains(driver).context_click(messaggio).perform()
        fase = "selezione del comando Inoltra"
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, SELETTORE_INOLTRO))
        ).click()
        fase = "conferma dell'immagine"
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, SELETTORE_CONFERMA_INOLTRO))
        ).click()

        fase = "apertura della scelta destinazione"
        dialog = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, SELETTORE_DIALOG))
        )
        fase = "ricerca della destinazione"
        ricerca = WebDriverWait(dialog, 10).until(
            EC.element_to_be_clickable((By.XPATH, SELETTORE_RICERCA_DESTINAZIONE))
        )
        ricerca.send_keys(destinazione)
        fase = "selezione della destinazione"
        WebDriverWait(dialog, 10).until(
            EC.element_to_be_clickable(
                (By.XPATH, f'.//span[@title="{destinazione}"]')
            )
        ).click()
        fase = "clic sul pulsante di invio"
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, SELETTORE_INVIO))
        ).click()

        fase = "conferma dell'invio"
        WebDriverWait(driver, 15).until(EC.invisibility_of_element(dialog))

        fase = "verifica dell'immagine inoltrata"
        WebDriverWait(driver, 15).until(
            lambda current_driver: current_driver.find_elements(
                By.XPATH, SELETTORE_MESSAGGIO_CON_IMMAGINE
            )
        )
        return True
    except (TimeoutException, WebDriverException) as errore:
        raise RuntimeError(f"Errore durante {fase}.") from errore


def main():
    driver = None
    fase = "avvio di Chrome"
    try:
        driver = configura_browser()
        fase = "apertura di WhatsApp"
        driver.get("https://whatsapp.com")
        fase = "clic sul pulsante Accedi"
        apri_whatsapp_web(driver)
        fase = "selezione della chat sorgente"
        seleziona_chat(driver, GRUPPO_SORGENTE)
        fase = "individuazione della prima immagine"
        messaggio = trova_prima_immagine(driver)
        fase = "inoltro alla chat di destinazione"
        if inoltra_immagine(driver, messaggio, GRUPPO_DESTINAZIONE):
            print(
                f"Inoltro richiesto: un'immagine da '{GRUPPO_SORGENTE}' a "
                f"'{GRUPPO_DESTINAZIONE}'."
            )
    except (RuntimeError, TimeoutException, WebDriverException) as errore:
        print(f"Invio non eseguito durante {fase}: {errore}")
    finally:
        if driver is not None:
            driver.quit()


if __name__ == "__main__":
    main()
