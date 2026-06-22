import unittest

import adaptive_core as core
import adaptive_launch
import combat_stats
import game_core as g
import neural_30s


class AdaptiveEmpireTests(unittest.TestCase):
    def test_neural_cadence_remains_thirty_seconds(self):
        self.assertEqual(neural_30s.NEURAL_DECISION_INTERVAL, 30.0)

    def test_correct_counter_mapping(self):
        original = __import__('imperial_mind').enemy_composition
        try:
            __import__('imperial_mind').enemy_composition = lambda realm: {
                'soldiers': g.D('.7'), 'archers': g.D('.2'), 'knights': g.D('.1')
            }
            self.assertEqual(adaptive_launch.correct_counter(g.Realm()), 'archer')
        finally:
            __import__('imperial_mind').enemy_composition = original

    def test_low_supply_uses_retreat_formation(self):
        state = core.AdaptiveState(supply='10', fatigue='20')
        formation = core.choose_formation(state, g.Realm())
        self.assertEqual(formation, 'Orderly Retreat')

    def test_logistics_consumes_supplies(self):
        state = core.AdaptiveState(supply='50')
        realm = g.Realm(soldiers=g.D(100), archers=g.D(50), knights=g.D(10))
        food_before = realm.food
        iron_before = realm.iron
        core.logistics_tick(state, realm, 1)
        self.assertLess(realm.food, food_before)
        self.assertLess(realm.iron, iron_before)

    def test_veterancy_bonus_is_capped(self):
        state = core.AdaptiveState(soldier_experience='100000000')
        self.assertLessEqual(core.veteran_bonus(state, 'soldiers'), g.D('.35'))

    def test_battle_learning_records_losses(self):
        state = core.AdaptiveState()
        realm = g.Realm(soldiers=g.D(8), archers=g.D(4), knights=g.D(1))
        previous = combat_stats.LAST_BATTLE.copy()
        try:
            combat_stats.LAST_BATTLE['result'] = 'Victory'
            combat_stats.LAST_BATTLE['rounds'] = 3
            combat_stats.LAST_BATTLE['friendly_losses'] = {
                'soldiers': g.D(2), 'archers': g.D(1), 'knights': g.D(0)
            }
            combat_stats.LAST_BATTLE['enemy_losses'] = {
                'soldiers': g.D(5), 'archers': g.D(2), 'knights': g.D(1)
            }
            self.assertTrue(core.learn_from_last_battle(state, realm))
            self.assertEqual(state.battles_observed, 1)
            self.assertEqual(g.D(state.units_lost), g.D(3))
        finally:
            combat_stats.LAST_BATTLE.clear()
            combat_stats.LAST_BATTLE.update(previous)


if __name__ == '__main__':
    unittest.main()
