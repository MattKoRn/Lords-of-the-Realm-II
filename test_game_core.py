import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import game_core as game


class GameCoreTests(unittest.TestCase):
    def test_decimal_combat_math(self):
        realm = game.Realm(archers=game.D(3), knights=game.D(2))
        self.assertGreater(realm.military_power(), 0)

    def test_huge_numbers_format_and_ai(self):
        realm = game.Realm(gold=game.D('1e10000'), threat=game.D('1e500'))
        self.assertTrue(game.fmt(realm.gold))
        ai = game.NeuralGovernor()
        self.assertIn(ai.choose(realm), ai.ACTIONS)

    def test_corrupt_ai_recovers(self):
        ai = game.NeuralGovernor({'w1': [[float('nan')]], 'generation': 'bad'})
        self.assertEqual(len(ai.w1), ai.hidden)
        self.assertEqual(ai.generation, 1)

    def test_save_round_trip_restores_decimals(self):
        with tempfile.TemporaryDirectory() as folder:
            save = Path(folder) / 'save.json'
            realm = game.Realm(gold=game.D('123456789.25'))
            with patch.object(game, 'SAVE_FILE', save), patch.object(game, 'SAVE_DIR', Path(folder)):
                game.save_realm(realm)
                loaded, _ = game.load_realm()
            self.assertIsInstance(loaded.gold, game.Decimal)
            self.assertEqual(loaded.gold, realm.gold)

    def test_damaged_save_is_quarantined(self):
        with tempfile.TemporaryDirectory() as folder:
            save = Path(folder) / 'save.json'
            save.write_text('{broken', encoding='utf-8')
            with patch.object(game, 'SAVE_FILE', save):
                loaded, offline = game.load_realm()
            self.assertIsInstance(loaded, game.Realm)
            self.assertEqual(offline, 0)
            self.assertTrue(Path(folder, 'save.corrupt.json').exists())

    def test_offline_tick_is_capped_and_safe(self):
        realm = game.Realm()
        realm.tick(game.MAX_OFFLINE * 10)
        self.assertLessEqual(realm.age, game.D(game.MAX_OFFLINE))
        self.assertGreaterEqual(realm.population, 10)


if __name__ == '__main__':
    unittest.main()
