import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import Mock, patch

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By

from whatsapp_bot import (
    apri_whatsapp_web,
    inoltra_immagine,
    main,
    trova_prima_immagine,
)


class FlussoSempliceTests(unittest.TestCase):
    @patch("whatsapp_bot.webdriver.ActionChains")
    @patch("whatsapp_bot.WebDriverWait")
    def test_apre_il_menu_della_prima_immagine_con_click_destro(
        self, attesa, action_chains
    ):
        driver = Mock()
        messaggio = Mock()
        menu = Mock()
        comando_inoltra = Mock()
        conferma = Mock()
        dialog = Mock()
        ricerca = Mock()
        destinazione = Mock()
        invio = Mock()
        attesa.return_value.until.side_effect = [
            menu,
            comando_inoltra,
            conferma,
            dialog,
            ricerca,
            destinazione,
            invio,
            True,
        ]

        inoltra_immagine(driver, messaggio, "Destinazione")

        action_chains.return_value.context_click.assert_called_once_with(messaggio)

    @patch("whatsapp_bot.EC.element_to_be_clickable")
    @patch("whatsapp_bot.webdriver.ActionChains")
    @patch("whatsapp_bot.WebDriverWait")
    def test_conferma_la_selezione_con_il_pulsante_inoltra_accessibile(
        self, attesa, action_chains, elemento_cliccabile
    ):
        attesa.return_value.until.side_effect = [Mock() for _ in range(8)]

        inoltra_immagine(Mock(), Mock(), "Destinazione")

        elemento_cliccabile.assert_any_call(
            (By.XPATH, '//*[@aria-label="Inoltra" or @aria-label="Forward"]')
        )

    @patch("whatsapp_bot.EC.element_to_be_clickable")
    @patch("whatsapp_bot.webdriver.ActionChains")
    @patch("whatsapp_bot.WebDriverWait")
    def test_cerca_la_destinazione_anche_con_un_input_normale(
        self, attesa, action_chains, elemento_cliccabile
    ):
        attesa.return_value.until.side_effect = [Mock() for _ in range(8)]

        inoltra_immagine(Mock(), Mock(), "Destinazione")

        elemento_cliccabile.assert_any_call(
            (
                By.XPATH,
                './/*[@role="textbox" or @contenteditable="true" or self::input]',
            )
        )

    @patch("whatsapp_bot.EC.element_to_be_clickable")
    @patch("whatsapp_bot.EC.invisibility_of_element")
    @patch("whatsapp_bot.webdriver.ActionChains")
    @patch("whatsapp_bot.WebDriverWait")
    def test_conferma_l_inoltro_con_il_bottone_freccia_visibile(
        self, attesa, action_chains, pannello_nascosto, elemento_cliccabile
    ):
        dialog = Mock()
        attesa.return_value.until.side_effect = [
            Mock(),
            Mock(),
            dialog,
            Mock(),
            Mock(),
            Mock(),
            True,
            [Mock()],
        ]

        inoltra_immagine(Mock(), Mock(), "Destinazione")

        elemento_cliccabile.assert_any_call(
            (
                By.XPATH,
                '//*[@role="button" and @aria-label="Invia"]',
            )
        )
        pannello_nascosto.assert_called_once_with(dialog)

    @patch("whatsapp_bot.configura_browser")
    def test_riporta_la_fase_che_fallisce(self, configura_browser):
        configura_browser.side_effect = WebDriverException("errore driver")

        with redirect_stdout(StringIO()) as output:
            main()

        self.assertIn("avvio di Chrome", output.getvalue())

    @patch("whatsapp_bot.WebDriverWait")
    def test_restituisce_la_prima_immagine_senza_filtri(self, attesa):
        prima = Mock(name="prima_immagine")
        riga = Mock(name="riga_messaggio")
        riga.find_element.return_value = prima
        driver = Mock()
        driver.find_elements.side_effect = lambda _, selettore: (
            [riga] if '@role="row"' in selettore else []
        )
        attesa.return_value.until.side_effect = (
            lambda condizione: condizione(driver)
        )

        risultato = trova_prima_immagine(driver)

        self.assertIs(prima, risultato)

    @patch("whatsapp_bot.WebDriverWait")
    def test_apre_whatsapp_web_con_il_pulsante_accedi(self, attesa):
        driver = Mock()
        driver.window_handles = ["finestra-principale"]
        pulsante_accedi = Mock()
        attesa.return_value.until.side_effect = [pulsante_accedi, True]

        apri_whatsapp_web(driver)

        pulsante_accedi.click.assert_called_once_with()
