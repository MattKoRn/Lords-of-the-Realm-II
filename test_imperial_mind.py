import unittest

import dynasty_ascendant as asc
import game_core as g
import imperial_mind as imperial
import neural_30s


class ImperialMindTests(unittest.TestCase):
    def test_decision_cadence_remains_thirty_seconds(self):
        self.assertEqual(neural_30s.NEURAL_DECISION_INTERVAL, 30.0)

    def test_recommends_counter_unit(self):
        realm = g.Realm(threat=g.D(100))
        self.assertIn(imperial.recommended_counter(realm), {'soldier', 'archer', 'knight'})

    def test_low_readiness_blocks_attack(self):
        game = object.__new__(imperial.Game)
        game.r = g.Realm(soldiers=g.D(1), threat=g.D(1000))
        game.asc = asc.AscendantState()
        allowed = imperial.improved_actions(game)
        self.assertNotIn('attack', allowed)

    def test_food_crisis_selects_rations(self):
        game = object.__new__(imperial.Game)
        game.r = g.Realm(food=g.D(1), population=g.D(1000))
        game.asc = asc.AscendantState()
        game.world = type('World', (), {'unlocked': [], 'research_value': g.D(0)})()
        self.assertEqual(imperial.select_policy(game), 'Emergency Rations')

    def test_policy_bonus_is_decimal_safe(self):
        state = imperial.ImperialState(policy='War Economy')
        self.assertEqual(imperial.policy_bonus(state, 'power'), g.D('.16'))


if __name__ == '__main__':
    unittest.main()
