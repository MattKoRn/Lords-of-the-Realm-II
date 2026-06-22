import random
import unittest

import combat_stats
import game_core as g


class CombatStatsTests(unittest.TestCase):
    def test_all_units_have_combat_stats(self):
        required = {'attack', 'defence', 'health', 'range', 'speed', 'morale', 'targets'}
        for unit in ('soldiers', 'archers', 'knights'):
            self.assertTrue(required.issubset(combat_stats.UNIT_STATS[unit]))

    def test_counter_relationships(self):
        self.assertGreater(combat_stats.COUNTERS[('archers', 'soldiers')], g.D(1))
        self.assertGreater(combat_stats.COUNTERS[('knights', 'archers')], g.D(1))
        self.assertGreater(combat_stats.COUNTERS[('soldiers', 'knights')], g.D(1))

    def test_damage_causes_whole_unit_deaths(self):
        killed = combat_stats.casualty_count(
            g.D(250), 'soldiers', g.D(100), g.D(1)
        )
        self.assertGreater(killed, 0)
        self.assertEqual(killed, killed.to_integral_value())

    def test_battle_can_kill_friendly_units(self):
        random.seed(7)
        realm = g.Realm(
            soldiers=g.D(120), archers=g.D(60), knights=g.D(15),
            threat=g.D(80), happiness=g.D(70)
        )
        before = realm.soldiers + realm.archers + realm.knights
        combat_stats.battle(realm)
        after = realm.soldiers + realm.archers + realm.knights
        self.assertLess(after, before)
        self.assertGreaterEqual(realm.soldiers, 0)
        self.assertGreaterEqual(realm.archers, 0)
        self.assertGreaterEqual(realm.knights, 0)

    def test_enemy_army_has_unit_composition(self):
        army = combat_stats.enemy_army(g.Realm(threat=g.D(50)), variance=False)
        self.assertEqual(set(army), {'soldiers', 'archers', 'knights'})
        self.assertGreater(sum(army.values(), g.D(0)), 0)


if __name__ == '__main__':
    unittest.main()
