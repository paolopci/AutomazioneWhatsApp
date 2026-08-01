import json
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, call, patch

from selenium.webdriver.common.by import By

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
    scegli_candidato,
    trova_immagini_nei_messaggi,
    main,
)


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
        self.assertIn("Conferma UI ricevuta e storico registrato.", messaggi)
        self.assertLess(
            messaggi.index("Conferma UI ricevuta e storico registrato."),
            messaggi.index("Invio eseguito:"),
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
            "//span[@title='Destinazione \"Sicura\"']",
            selettore,
        )


class InoltroMessaggioTests(unittest.TestCase):
    @patch("whatsapp_bot.webdriver.ActionChains")
    @patch("whatsapp_bot.EC.staleness_of", return_value="conferma_invio")
    @patch("whatsapp_bot.EC.element_to_be_clickable")
    @patch("whatsapp_bot.WebDriverWait")
    def test_attende_la_conferma_ui_e_seleziona_destinazione_esatta(
        self, attesa, elemento_cliccabile, staleness_of, action_chains
    ):
        driver = Mock()
        messaggio = Mock()
        menu = Mock()
        ricerca_destinazione = Mock()
        risultato_destinazione = Mock()
        pulsante_invio = Mock()
        attesa.return_value.until.side_effect = [
            menu,
            Mock(),
            Mock(),
            ricerca_destinazione,
            risultato_destinazione,
            pulsante_invio,
            True,
        ]

        esito = inoltra_messaggio(driver, messaggio, 'Destinazione "Sicura"')

        self.assertTrue(esito)
        action_chains.assert_called_once_with(driver)
        action_chains.return_value.move_to_element.assert_called_once_with(messaggio)
        ricerca_destinazione.send_keys.assert_called_once_with('Destinazione "Sicura"')
        risultato_destinazione.click.assert_called_once_with()
        pulsante_invio.click.assert_called_once_with()
        elemento_cliccabile.assert_any_call(
            (By.XPATH, "//span[@title='Destinazione \"Sicura\"']")
        )
        staleness_of.assert_called_once_with(pulsante_invio)
        attesa.return_value.until.assert_any_call("conferma_invio")
        self.assertEqual(call(driver, 15), attesa.call_args_list[-1])


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


class ScansioneImmaginiTests(unittest.TestCase):
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

    @patch("whatsapp_bot.scorri_cronologia_verso_alto", return_value=True)
    @patch("whatsapp_bot.trova_immagini_nei_messaggi", return_value=[])
    def test_non_supera_il_numero_massimo_di_scorrimenti(
        self, trova_immagini, scorri
    ):
        self.assertEqual([], raccogli_candidati(Mock(), [], max_scorrimenti=20))
        self.assertEqual(20, scorri.call_count)
