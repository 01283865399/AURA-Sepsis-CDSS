"""Deterministic unit tests for DDXPlus data and feature encoding helpers."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

SPEC = importlib.util.spec_from_file_location(
    "ddxplus_training_helpers", SCRIPTS / "04_train_ddxplus.py"
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Could not load DDXPlus training helpers.")
DDX_TRAINING = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DDX_TRAINING)


class DDXPlusTrainingTests(unittest.TestCase):
    def test_evidence_parser_accepts_json_and_actual_single_quote_format(self) -> None:
        self.assertEqual(
            DDX_TRAINING.parse_evidence('["E_48", "E_54_@_V_161"]'),
            ["E_48", "E_54_@_V_161"],
        )
        self.assertEqual(
            DDX_TRAINING.parse_evidence("['E_48', 'E_54_@_V_161']"),
            ["E_48", "E_54_@_V_161"],
        )
        with self.assertRaises(ValueError):
            DDX_TRAINING.parse_evidence("__import__('os').system('echo unsafe')")

    def test_evidence_encoding_fits_exact_model_input_without_token_collisions(self) -> None:
        schema = {
            "E_1": {"data_type": "B"},
            "E_2": {"data_type": "C", "possible-values": ["V_1", "V_2"]},
            "E_3": {"data_type": "M", "possible-values": ["V_3", "V_4", "V_5"]},
        }
        vocabulary = DDX_TRAINING.make_feature_vocab(schema)
        multi_tokens = [key for key in vocabulary if key.startswith("E_3_@_")]

        self.assertEqual(vocabulary["E_1"], [2])
        self.assertEqual(len(vocabulary["E_2_@_V_1"]), 1)
        self.assertTrue(all(len(vocabulary[token]) == 3 for token in multi_tokens))
        self.assertEqual(
            len({tuple(vocabulary[token]) for token in multi_tokens}),
            len(multi_tokens),
        )
        self.assertTrue(
            all(
                2 <= index < DDX_TRAINING.INPUT_SIZE
                for indexes in vocabulary.values()
                for index in indexes
            )
        )

    def test_network_uses_requested_512_256_128_49_layers(self) -> None:
        import torch

        model = DDX_TRAINING.make_model(torch, 49)
        self.assertEqual(tuple(model(torch.zeros((2, 512))).shape), (2, 49))
        self.assertEqual(model[0].in_features, 512)
        self.assertEqual(model[0].out_features, 256)
        self.assertEqual(model[3].out_features, 128)
        self.assertEqual(model[6].out_features, 49)


if __name__ == "__main__":
    unittest.main()
