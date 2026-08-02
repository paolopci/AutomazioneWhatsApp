import json
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, PropertyMock, call, patch

from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By

import whatsapp_bot
from whatsapp_bot import (
    CandidatoImmagine,
    PERCORSO_STORICO,
    carica_storico,
    crea_selettore_destinazione,
    esegui_invio_immagine,
    inoltra_messaggio,
    registra_invio,
    raccogli_candidati,
    salva_storico,
    scorri_cronologia_verso_alto,
    scegli_candidato,
    trova_immagini_nei_messaggi,
    trova_campo_ricerca_visibile,
    main,
)


class OrchestrazioneInvioTests(unittest.TestCase):
    @patch("whatsapp_bot.registra_invio")
    @patch("whatsapp_bot.inoltra_messaggio", return_value=True)
    @patch("whatsapp_bot.raccogli_candidati")
    def test_riacquisisce_il_messaggio_subito_prima_dell_inoltro(
        self, raccogli, inoltra, registra
    ):
        impronta = "d" * 64
        candidato_iniziale = CandidatoImmagine(
            "messaggio_obsoleto", "immagine_obsoleta", impronta
        )
        candidato_aggiornato = CandidatoImmagine(
            "messaggio_aggiornato", "immagine_aggiornata", impronta
        )
        raccogli.side_effect = [[candidato_iniziale], [candidato_aggiornato]]
        driver = Mock()

        esito = esegui_invio_immagine(
            driver,
            "Destinazione",
            [],
            "storico.json",
        )

        self.assertTrue(esito)
        inoltra.assert_called_once_with(
            driver,
            candidato_aggiornato.messaggio,
            "Destinazione",
        )
        registra.assert_called_once_with("storico.json", [], impronta)

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

    @patch("whatsapp_bot.registra_invio")
    @patch("whatsapp_bot.inoltra_messaggio", return_value=True)
    @patch("whatsapp_bot.raccogli_candidati")
    def test_registra_solo_dopo_inoltro_confermato(
        self, raccogli, inoltra, registra
    ):
        candidato = CandidatoImmagine("messaggio", "immagine", "f" * 64)
        raccogli.return_value = [candidato]
        driver = Mock()

        esito = esegui_invio_immagine(driver, "Destinazione", [], "storico.json")

        self.assertTrue(esito)
        inoltra.assert_called_once_with(driver, candidato.messaggio, "Destinazione")
        registra.assert_called_once_with("storico.json", [], "f" * 64)


class MainTests(unittest.TestCase):
    def setUp(self):
        self.lock = Mock(name="lock_istanza")
        self.acquisisci_lock = patch(
            "whatsapp_bot.acquisisci_lock_istanza",
            return_value=self.lock,
            create=True,
        ).start()
        self.rilascia_lock = patch(
            "whatsapp_bot.rilascia_lock_istanza",
            create=True,
        ).start()
        self.addCleanup(patch.stopall)

    @patch("whatsapp_bot.time.sleep")
    @patch("whatsapp_bot.esegui_invio_immagine")
    @patch("whatsapp_bot.cerca_e_seleziona_chat", return_value=True)
    @patch("whatsapp_bot.accedi_a_whatsapp_web")
    @patch("whatsapp_bot.configura_browser")
    @patch("whatsapp_bot.carica_storico")
    def test_stampa_successo_dopo_conferma_invio_e_registrazione_storico(
        self,
        carica_storico,
        configura_browser,
        accedi,
        cerca_chat,
        esegui_invio,
        sleep,
    ):
        storico = ["a" * 64]
        driver = Mock()
        carica_storico.return_value = storico
        configura_browser.return_value = driver

        def invio_confermato(*_):
            print("Conferma UI ricevuta e storico registrato.")
            return True

        esegui_invio.side_effect = invio_confermato
        output = io.StringIO()

        with redirect_stdout(output):
            main()

        messaggi = output.getvalue()
        messaggio_successo = (
            "Invio eseguito: una nuova immagine da 'Rosario' "
            "è stata inviata a 'Destinazione'."
        )
        self.assertIn("Conferma UI ricevuta e storico registrato.", messaggi)
        self.assertEqual(1, messaggi.count(messaggio_successo))
        self.assertLess(
            messaggi.index("Conferma UI ricevuta e storico registrato."),
            messaggi.index(messaggio_successo),
        )
        carica_storico.assert_called_once()
        driver.get.assert_called_once_with("https://whatsapp.com")
        accedi.assert_called_once_with(driver)
        cerca_chat.assert_called_once_with(driver, "Rosario")
        esegui_invio.assert_called_once_with(
            driver, "Destinazione", storico, PERCORSO_STORICO
        )
        sleep.assert_called_once_with(5)
        driver.quit.assert_called_once_with()

    def test_lock_copre_caricamento_inoltro_persistenza_e_chiusura(self):
        acquisisci = getattr(whatsapp_bot, "acquisisci_lock_istanza", None)
        rilascia = getattr(whatsapp_bot, "rilascia_lock_istanza", None)
        self.assertTrue(callable(acquisisci), "Manca acquisisci_lock_istanza")
        self.assertTrue(callable(rilascia), "Manca rilascia_lock_istanza")

        eventi = []
        candidato = CandidatoImmagine("messaggio", "immagine", "b" * 64)
        driver = Mock()
        driver.quit.side_effect = lambda: eventi.append("chiusura")
        self.acquisisci_lock.side_effect = lambda _: eventi.append("lock") or self.lock
        self.rilascia_lock.side_effect = lambda _: eventi.append("release")

        with (
            patch(
                "whatsapp_bot.carica_storico",
                side_effect=lambda _: eventi.append("carica") or [],
            ),
            patch("whatsapp_bot.configura_browser", return_value=driver),
            patch("whatsapp_bot.accedi_a_whatsapp_web"),
            patch("whatsapp_bot.cerca_e_seleziona_chat", return_value=True),
            patch(
                "whatsapp_bot.raccogli_candidati",
                return_value=[candidato],
            ),
            patch(
                "whatsapp_bot.inoltra_messaggio",
                side_effect=lambda *_: eventi.append("inoltro") or True,
            ),
            patch(
                "whatsapp_bot.registra_invio",
                side_effect=lambda *_: eventi.append("persistenza"),
            ),
            patch("whatsapp_bot.time.sleep"),
            redirect_stdout(io.StringIO()),
        ):
            main()

        self.assertEqual(
            ["lock", "carica", "inoltro", "persistenza", "chiusura", "release"],
            eventi,
        )

    def test_seconda_istanza_si_ferma_prima_di_caricare_o_inoltrare(self):
        errore_lock = getattr(whatsapp_bot, "ErroreIstanzaGiaInEsecuzione", None)
        self.assertIsNotNone(errore_lock, "Manca ErroreIstanzaGiaInEsecuzione")
        self.acquisisci_lock.side_effect = errore_lock("bot già in esecuzione")
        output = io.StringIO()

        with (
            patch("whatsapp_bot.carica_storico") as carica_storico,
            patch("whatsapp_bot.inoltra_messaggio") as inoltra,
            redirect_stdout(output),
        ):
            main()

        self.assertIn("già in esecuzione", output.getvalue())
        carica_storico.assert_not_called()
        inoltra.assert_not_called()
        self.rilascia_lock.assert_not_called()

    def test_avvisa_di_non_riavviare_dopo_invio_senza_storico_persistito(self):
        candidato = CandidatoImmagine("messaggio", "immagine", "a" * 64)
        driver = Mock()
        output = io.StringIO()

        with tempfile.TemporaryDirectory() as directory:
            percorso_storico = os.path.join(directory, "storico_invii.json")
            with (
                patch("whatsapp_bot.PERCORSO_STORICO", percorso_storico),
                patch("whatsapp_bot.configura_browser", return_value=driver),
                patch("whatsapp_bot.accedi_a_whatsapp_web"),
                patch("whatsapp_bot.cerca_e_seleziona_chat", return_value=True),
                patch("whatsapp_bot.raccogli_candidati", return_value=[candidato]),
                patch("whatsapp_bot.inoltra_messaggio", return_value=True),
                patch("whatsapp_bot.os.replace", side_effect=OSError("disco pieno")),
                patch("whatsapp_bot.time.sleep"),
                redirect_stdout(output),
            ):
                main()

        messaggi = output.getvalue()
        self.assertIn(
            "Invio eseguito, ma lo storico non è stato salvato.",
            messaggi,
        )
        self.assertIn(
            "Non avviare nuovamente il bot finché il problema non è risolto.",
            messaggi,
        )
        self.assertNotIn(
            "Invio eseguito: una nuova immagine da 'Rosario' "
            "è stata inviata a 'Destinazione'.",
            messaggi,
        )
        driver.quit.assert_called_once_with()

    @patch("whatsapp_bot.time.sleep")
    @patch("whatsapp_bot.esegui_invio_immagine", return_value=False)
    @patch("whatsapp_bot.cerca_e_seleziona_chat", return_value=True)
    @patch("whatsapp_bot.accedi_a_whatsapp_web")
    @patch("whatsapp_bot.configura_browser")
    @patch("whatsapp_bot.carica_storico", return_value=[])
    def test_non_stampa_successo_quando_non_esegue_invio(
        self,
        carica_storico,
        configura_browser,
        accedi,
        cerca_chat,
        esegui_invio,
        sleep,
    ):
        driver = Mock()
        configura_browser.return_value = driver
        output = io.StringIO()

        with redirect_stdout(output):
            main()

        self.assertNotIn("Invio eseguito:", output.getvalue())
        esegui_invio.assert_called_once_with(
            driver, "Destinazione", [], PERCORSO_STORICO
        )
        sleep.assert_called_once_with(5)
        driver.quit.assert_called_once_with()

    @patch("whatsapp_bot.time.sleep")
    @patch("whatsapp_bot.accedi_a_whatsapp_web", side_effect=RuntimeError("accesso"))
    @patch("whatsapp_bot.configura_browser")
    @patch("whatsapp_bot.carica_storico", return_value=[])
    def test_chiude_il_browser_e_comunica_errore_se_l_accesso_fallisce(
        self, carica_storico, configura_browser, accedi, sleep
    ):
        driver = Mock()
        configura_browser.return_value = driver
        output = io.StringIO()

        with redirect_stdout(output):
            main()

        self.assertIn("Invio non eseguito: accesso", output.getvalue())
        sleep.assert_called_once_with(5)
        driver.quit.assert_called_once_with()


class SelettoreDestinazioneTests(unittest.TestCase):
    def test_crea_un_literal_xpath_valido_con_virgolette_doppie(self):
        selettore = crea_selettore_destinazione('Destinazione "Sicura"')

        self.assertEqual(
            ".//span[@title='Destinazione \"Sicura\"']",
            selettore,
        )

    def test_ricerca_globale_accetta_solo_contenteditable_true(self):
        driver = Mock()
        driver.find_elements.return_value = []

        self.assertFalse(trova_campo_ricerca_visibile(driver))

        driver.find_elements.assert_called_once_with(
            By.XPATH,
            '//*[@role="textbox" or @contenteditable="true" or self::input]',
        )


class InoltroMessaggioTests(unittest.TestCase):
    @patch("whatsapp_bot.webdriver.ActionChains")
    @patch(
        "whatsapp_bot.EC.invisibility_of_element",
        return_value="pannello_chiuso",
    )
    @patch(
        "whatsapp_bot.EC.visibility_of_element_located",
        return_value="pannello_visibile",
    )
    @patch("whatsapp_bot.EC.element_to_be_clickable")
    @patch("whatsapp_bot.WebDriverWait")
    def test_usa_il_menu_visibile_se_si_trova_fuori_dal_contenitore(
        self,
        attesa,
        elemento_cliccabile,
        pannello_visibile,
        pannello_nascosto,
        action_chains,
    ):
        driver = Mock()
        messaggio = Mock()
        messaggio.find_elements.return_value = []
        menu_globale = Mock()
        menu_globale.is_displayed.return_value = True
        menu_globale.is_enabled.return_value = True
        driver.find_elements.return_value = [menu_globale]
        azione_inoltro = Mock()
        conferma_inoltro = Mock()
        pannello_inoltro = Mock()
        ricerca_destinazione = Mock()
        risultato_destinazione = Mock()
        pulsante_invio = Mock()
        attesa.return_value.until.side_effect = [
            azione_inoltro,
            conferma_inoltro,
            pannello_inoltro,
            ricerca_destinazione,
            risultato_destinazione,
            pulsante_invio,
            True,
        ]

        esito = inoltra_messaggio(driver, messaggio, "Destinazione")

        self.assertTrue(esito)
        menu_globale.click.assert_called_once_with()
        action_chains.return_value.context_click.assert_not_called()

    @patch("whatsapp_bot.webdriver.ActionChains")
    @patch(
        "whatsapp_bot.EC.invisibility_of_element",
        return_value="pannello_chiuso",
    )
    @patch(
        "whatsapp_bot.EC.visibility_of_element_located",
        return_value="pannello_visibile",
    )
    @patch("whatsapp_bot.EC.element_to_be_clickable")
    @patch("whatsapp_bot.WebDriverWait")
    def test_apre_il_menu_con_click_destro_se_la_freccia_non_esiste(
        self,
        attesa,
        elemento_cliccabile,
        pannello_visibile,
        pannello_nascosto,
        action_chains,
    ):
        driver = Mock()
        driver.find_elements.return_value = []
        messaggio = Mock()
        messaggio.find_elements.return_value = []
        azione_inoltro = Mock()
        conferma_inoltro = Mock()
        pannello_inoltro = Mock()
        ricerca_destinazione = Mock()
        risultato_destinazione = Mock()
        pulsante_invio = Mock()
        attesa.return_value.until.side_effect = [
            azione_inoltro,
            conferma_inoltro,
            pannello_inoltro,
            ricerca_destinazione,
            risultato_destinazione,
            pulsante_invio,
            True,
        ]

        esito = inoltra_messaggio(driver, messaggio, "Destinazione")

        self.assertTrue(esito)
        action_chains.return_value.context_click.assert_called_once_with(messaggio)
        azione_inoltro.click.assert_called_once_with()
        elemento_cliccabile.assert_any_call(
            (
                By.XPATH,
                '//*[(@role="button" or @role="menuitem" or '
                '(self::div and @tabindex="0")) and ('
                '@aria-label="Inoltra" or @aria-label="Forward message" or '
                '@aria-label="Forward" or normalize-space(.)="Inoltra" or '
                'normalize-space(.)="Forward")]',
            )
        )

    @patch("whatsapp_bot.webdriver.ActionChains")
    @patch("whatsapp_bot.WebDriverWait")
    def test_timeout_indica_la_fase_di_apertura_del_menu(
        self, attesa, action_chains
    ):
        attesa.return_value.until.side_effect = TimeoutException()

        with self.assertRaisesRegex(
            RuntimeError,
            "apertura del menu contestuale del messaggio",
        ):
            inoltra_messaggio(Mock(), Mock(), "Destinazione")

    @patch("whatsapp_bot.webdriver.ActionChains")
    @patch(
        "whatsapp_bot.EC.invisibility_of_element",
        return_value="pannello_chiuso",
    )
    @patch(
        "whatsapp_bot.EC.visibility_of_element_located",
        return_value="pannello_visibile",
    )
    @patch("whatsapp_bot.EC.element_to_be_clickable")
    @patch("whatsapp_bot.WebDriverWait")
    def test_limita_i_controlli_al_pannello_e_attende_la_sua_chiusura(
        self,
        attesa,
        elemento_cliccabile,
        pannello_visibile,
        pannello_nascosto,
        action_chains,
    ):
        driver = Mock()
        messaggio = Mock()
        menu = Mock()
        azione_inoltro = Mock()
        conferma_inoltro = Mock()
        pannello_inoltro = Mock()
        ricerca_destinazione = Mock()
        risultato_destinazione = Mock()
        pulsante_invio = Mock()
        attesa.return_value.until.side_effect = [
            menu,
            azione_inoltro,
            conferma_inoltro,
            pannello_inoltro,
            ricerca_destinazione,
            risultato_destinazione,
            pulsante_invio,
            True,
        ]
        output = io.StringIO()

        with redirect_stdout(output):
            esito = inoltra_messaggio(driver, messaggio, 'Destinazione "Sicura"')

        self.assertTrue(esito)
        self.assertEqual("", output.getvalue())
        action_chains.assert_called_once_with(driver)
        action_chains.return_value.move_to_element.assert_called_once_with(messaggio)
        ricerca_destinazione.send_keys.assert_called_once_with('Destinazione "Sicura"')
        risultato_destinazione.click.assert_called_once_with()
        pulsante_invio.click.assert_called_once_with()
        elemento_cliccabile.assert_any_call(
            (By.XPATH, './/span[@data-icon="down-context"]')
        )
        pannello_visibile.assert_called_once_with(
            (
                By.XPATH,
                '//*[@role="dialog" and '
                './/*[@role="textbox" and @contenteditable="true"]]',
            )
        )
        elemento_cliccabile.assert_any_call(
            (By.XPATH, './/*[@role="textbox" and @contenteditable="true"]')
        )
        elemento_cliccabile.assert_any_call(
            (By.XPATH, ".//span[@title='Destinazione \"Sicura\"']")
        )
        elemento_cliccabile.assert_any_call(
            (By.XPATH, './/span[@data-icon="send"]')
        )
        pannello_nascosto.assert_called_once_with(pannello_inoltro)
        attesa.return_value.until.assert_any_call("pannello_chiuso")
        self.assertEqual(
            [
                call(messaggio, 10),
                call(driver, 10),
                call(driver, 10),
                call(driver, 10),
                call(pannello_inoltro, 10),
                call(pannello_inoltro, 10),
                call(pannello_inoltro, 10),
                call(driver, 15),
            ],
            attesa.call_args_list,
        )


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

    def test_ogni_salvataggio_usa_un_file_temporaneo_univoco(self):
        sorgenti_temporanee = []
        replace_reale = os.replace

        def registra_replace(sorgente, destinazione):
            sorgenti_temporanee.append(sorgente)
            replace_reale(sorgente, destinazione)

        with patch("whatsapp_bot.os.replace", side_effect=registra_replace):
            salva_storico(self.percorso, ["1" * 64])
            salva_storico(self.percorso, ["2" * 64])

        self.assertEqual(2, len(sorgenti_temporanee))
        self.assertNotEqual(*sorgenti_temporanee)

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


class ImmagineFinta:
    def __init__(self, visibile, alt, larghezza, altezza):
        self.visibile = visibile
        self.alt = alt
        self.larghezza = larghezza
        self.altezza = altezza

    def is_displayed(self):
        return self.visibile

    def get_attribute(self, nome):
        return self.alt if nome == "alt" else None


class MessaggioFinto:
    def __init__(self, immagini):
        self.immagini = immagini

    def find_elements(self, *_):
        return self.immagini


class DriverFinto:
    def __init__(self, messaggi):
        self.messaggi = messaggi

    def find_elements(self, *_):
        return self.messaggi

    def execute_script(self, _, immagine):
        return [immagine.larghezza, immagine.altezza]


class ScorrimentoCronologiaTests(unittest.TestCase):
    @patch("whatsapp_bot.WebDriverWait")
    def test_usa_il_primo_antenato_con_overflow_verticale_scrollabile(
        self, attesa
    ):
        riga = Mock(name="riga")
        riga.id = "riga-corrente"
        antenato_non_scrollabile = Mock(name="contenitore_non_scrollabile")
        contenitore_scroll = Mock(name="contenitore_scroll")
        riga.find_element.return_value = antenato_non_scrollabile
        antenato_non_scrollabile.find_element.return_value = contenitore_scroll
        driver = Mock()
        driver.find_elements.return_value = [riga]
        driver.execute_script.side_effect = [
            {"scorrevole": False},
            {"scorrevole": False},
            {"scorrevole": True},
            True,
        ]
        attesa.return_value.until.return_value = True

        esito = scorri_cronologia_verso_alto(driver)

        self.assertTrue(esito)
        self.assertIs(
            contenitore_scroll,
            driver.execute_script.call_args_list[-1].args[1],
        )

    @patch("whatsapp_bot.WebDriverWait")
    def test_usa_una_direzione_negativa_anche_da_scrolltop_zero(
        self, attesa
    ):
        riga = Mock()
        riga.id = "riga-corrente"
        driver = Mock()
        driver.find_elements.return_value = [riga]

        def simula_contenitore_column_reverse(script, elemento, *argomenti):
            if not argomenti:
                return {"scorrevole": True}
            direzione = argomenti[0]
            posizione_iniziale = 0
            posizione_finale = posizione_iniziale + direzione * 100
            return posizione_finale < posizione_iniziale

        driver.execute_script.side_effect = simula_contenitore_column_reverse
        attesa.return_value.until.return_value = True

        esito = scorri_cronologia_verso_alto(driver)

        self.assertTrue(esito)

    @patch("whatsapp_bot.WebDriverWait")
    def test_ritrova_la_riga_se_whatsapp_aggiorna_il_dom(
        self, attesa
    ):
        riga_obsoleta = Mock()
        type(riga_obsoleta).id = PropertyMock(
            side_effect=StaleElementReferenceException()
        )
        riga_aggiornata = Mock()
        riga_aggiornata.id = "riga-aggiornata"
        driver = Mock()
        driver.find_elements.side_effect = [
            [riga_obsoleta],
            [riga_aggiornata],
        ]
        driver.execute_script.side_effect = [
            {"scorrevole": True},
            True,
        ]
        attesa.return_value.until.return_value = True

        esito = scorri_cronologia_verso_alto(driver)

        self.assertTrue(esito)
        self.assertEqual(2, driver.find_elements.call_count)
        self.assertEqual(2, driver.execute_script.call_count)


class ScansioneImmaginiTests(unittest.TestCase):
    def _crea_scenario_con_errore_transitorio(self, fase, errore):
        prima_immagine = Mock(name="prima_immagine")
        prima_immagine.is_displayed.return_value = True
        prima_immagine.get_attribute.return_value = "Foto"
        primo_messaggio = Mock(name="primo_messaggio")
        primo_messaggio.find_elements.return_value = [prima_immagine]

        immagine_valida = Mock(name="immagine_valida")
        immagine_valida.is_displayed.return_value = True
        immagine_valida.get_attribute.return_value = "Foto"
        messaggio_valido = Mock(name="messaggio_valido")
        messaggio_valido.find_elements.return_value = [immagine_valida]

        driver = Mock(name="driver")
        driver.find_elements.return_value = [primo_messaggio, messaggio_valido]

        if fase == "messaggio.find_elements":
            primo_messaggio.find_elements.side_effect = errore
        elif fase == "is_displayed":
            prima_immagine.is_displayed.side_effect = errore
        elif fase == "get_attribute":
            prima_immagine.get_attribute.side_effect = errore

        def leggi_dimensioni(_, immagine):
            if fase == "dimensioni" and immagine is prima_immagine:
                raise errore
            return [120, 120]

        driver.execute_script.side_effect = leggi_dimensioni
        return driver, messaggio_valido, immagine_valida

    def test_include_immagine_visibile_con_dimensioni_naturali_idonee(self):
        immagine = ImmagineFinta(True, "Foto", 120, 120)
        messaggio = MessaggioFinto([immagine])

        risultati = trova_immagini_nei_messaggi(DriverFinto([messaggio]))

        self.assertEqual([(messaggio, immagine)], risultati)

    def test_esclude_avatar_con_almeno_una_dimensione_inferiore_a_120(self):
        avatar = ImmagineFinta(True, "Avatar", 119, 300)
        messaggio = MessaggioFinto([avatar])

        risultati = trova_immagini_nei_messaggi(DriverFinto([messaggio]))

        self.assertEqual([], risultati)

    def test_esclude_sticker_indipendentemente_dal_maiuscolo_minuscolo(self):
        sticker = ImmagineFinta(True, "Sticker animato", 300, 300)
        messaggio = MessaggioFinto([sticker])

        risultati = trova_immagini_nei_messaggi(DriverFinto([messaggio]))

        self.assertEqual([], risultati)

    def test_esclude_immagine_nascosta(self):
        immagine_nascosta = ImmagineFinta(False, "Foto", 300, 300)
        messaggio = MessaggioFinto([immagine_nascosta])

        risultati = trova_immagini_nei_messaggi(DriverFinto([messaggio]))

        self.assertEqual([], risultati)

    def test_stale_in_ogni_fase_ignora_elemento_e_prosegue(self):
        fasi = (
            "messaggio.find_elements",
            "is_displayed",
            "get_attribute",
            "dimensioni",
        )

        for fase in fasi:
            with self.subTest(fase=fase):
                driver, messaggio_valido, immagine_valida = (
                    self._crea_scenario_con_errore_transitorio(
                        fase,
                        StaleElementReferenceException(f"stale in {fase}"),
                    )
                )

                try:
                    with redirect_stdout(io.StringIO()):
                        risultati = trova_immagini_nei_messaggi(driver)
                except StaleElementReferenceException as errore:
                    self.fail(f"Stale propagato dalla fase {fase}: {errore}")

                self.assertEqual([(messaggio_valido, immagine_valida)], risultati)

    def test_timeout_per_messaggio_o_immagine_non_blocca_i_successivi(self):
        for fase in ("messaggio.find_elements", "dimensioni"):
            with self.subTest(fase=fase):
                driver, messaggio_valido, immagine_valida = (
                    self._crea_scenario_con_errore_transitorio(
                        fase,
                        TimeoutException(f"timeout in {fase}"),
                    )
                )

                try:
                    with redirect_stdout(io.StringIO()):
                        risultati = trova_immagini_nei_messaggi(driver)
                except TimeoutException as errore:
                    self.fail(f"Timeout propagato dalla fase {fase}: {errore}")

                self.assertEqual([(messaggio_valido, immagine_valida)], risultati)

    def test_webdriver_exception_generico_della_scansione_viene_propagato(self):
        driver, _, _ = self._crea_scenario_con_errore_transitorio(
            "get_attribute",
            WebDriverException("sessione terminata"),
        )

        with self.assertRaisesRegex(WebDriverException, "sessione terminata"):
            trova_immagini_nei_messaggi(driver)


class RaccoltaCandidatiTests(unittest.TestCase):
    @patch("whatsapp_bot.calcola_impronta_immagine", return_value="c" * 64)
    @patch("whatsapp_bot.scorri_cronologia_verso_alto")
    @patch("whatsapp_bot.trova_immagini_nei_messaggi")
    def test_prova_la_direzione_opposta_se_la_prima_e_bloccata(
        self, trova_immagini, scorri, calcola_impronta
    ):
        messaggio = Mock()
        immagine = Mock()
        trova_immagini.side_effect = [[], [(messaggio, immagine)]]
        scorri.side_effect = [False, True]
        driver = Mock()

        candidati = raccogli_candidati(driver, [], max_scorrimenti=20)

        self.assertEqual(["c" * 64], [candidato.impronta for candidato in candidati])
        self.assertEqual(
            [call(driver, -1), call(driver, 1)],
            scorri.call_args_list,
        )

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
        driver = Mock()

        self.assertEqual([], raccogli_candidati(driver, [], max_scorrimenti=20))
        self.assertEqual(
            [call(driver, -1), call(driver, 1)],
            scorri.call_args_list,
        )

    @patch("whatsapp_bot.scorri_cronologia_verso_alto", return_value=True)
    @patch("whatsapp_bot.trova_immagini_nei_messaggi", return_value=[])
    def test_non_supera_il_numero_massimo_di_scorrimenti(
        self, trova_immagini, scorri
    ):
        self.assertEqual([], raccogli_candidati(Mock(), [], max_scorrimenti=20))
        self.assertEqual(20, scorri.call_count)

    @patch("whatsapp_bot.calcola_impronta_immagine")
    @patch("whatsapp_bot.trova_immagini_nei_messaggi")
    def test_stale_di_un_candidato_non_blocca_i_successivi(
        self, trova_immagini, calcola_impronta
    ):
        primo = (Mock(), Mock())
        secondo = (Mock(), Mock())
        trova_immagini.return_value = [primo, secondo]
        calcola_impronta.side_effect = [
            StaleElementReferenceException("candidato stale"),
            "3" * 64,
        ]

        with redirect_stdout(io.StringIO()):
            candidati = raccogli_candidati(Mock(), [], max_scorrimenti=0)

        self.assertEqual(["3" * 64], [candidato.impronta for candidato in candidati])
        self.assertEqual(2, calcola_impronta.call_count)

    @patch("whatsapp_bot.calcola_impronta_immagine")
    @patch("whatsapp_bot.trova_immagini_nei_messaggi")
    def test_timeout_di_un_candidato_non_blocca_i_successivi(
        self, trova_immagini, calcola_impronta
    ):
        primo = (Mock(), Mock())
        secondo = (Mock(), Mock())
        trova_immagini.return_value = [primo, secondo]
        calcola_impronta.side_effect = [TimeoutException("candidato lento"), "4" * 64]

        with redirect_stdout(io.StringIO()):
            candidati = raccogli_candidati(Mock(), [], max_scorrimenti=0)

        self.assertEqual(["4" * 64], [candidato.impronta for candidato in candidati])
        self.assertEqual(2, calcola_impronta.call_count)

    @patch("whatsapp_bot.calcola_impronta_immagine")
    @patch("whatsapp_bot.trova_immagini_nei_messaggi")
    def test_errore_fatale_della_sessione_non_viene_nascosto(
        self, trova_immagini, calcola_impronta
    ):
        trova_immagini.return_value = [(Mock(), Mock())]
        calcola_impronta.side_effect = WebDriverException("sessione terminata")

        with self.assertRaisesRegex(WebDriverException, "sessione terminata"):
            raccogli_candidati(Mock(), [], max_scorrimenti=0)


class LockIstanzaTests(unittest.TestCase):
    def test_contesa_del_lock_restituisce_un_errore_utile(self):
        acquisisci = getattr(whatsapp_bot, "acquisisci_lock_istanza", None)
        errore_lock = getattr(whatsapp_bot, "ErroreIstanzaGiaInEsecuzione", None)
        self.assertTrue(callable(acquisisci), "Manca acquisisci_lock_istanza")
        self.assertIsNotNone(errore_lock, "Manca ErroreIstanzaGiaInEsecuzione")

        with tempfile.TemporaryDirectory() as directory:
            percorso = os.path.join(directory, ".whatsapp_bot.lock")
            with patch("whatsapp_bot.msvcrt.locking", side_effect=OSError("busy")):
                with self.assertRaisesRegex(errore_lock, "già in esecuzione"):
                    acquisisci(percorso)
