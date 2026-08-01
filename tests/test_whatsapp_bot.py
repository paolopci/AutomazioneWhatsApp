import json
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from whatsapp_bot import (
    CandidatoImmagine,
    carica_storico,
    registra_invio,
    raccogli_candidati,
    salva_storico,
    scegli_candidato,
    trova_immagini_nei_messaggi,
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
