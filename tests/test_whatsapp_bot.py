import json
import os
import tempfile
import unittest

from whatsapp_bot import (
    CandidatoImmagine,
    carica_storico,
    registra_invio,
    salva_storico,
    scegli_candidato,
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
