import unittest

import autonomous_mode as auto
import dynasty_ascendant as asc
import game_core as g
import kingdom_evolved as evolved


class DynastyAscendantTests(unittest.TestCase):
    def test_action_mask_blocks_unaffordable_buildings(self):
        realm = g.Realm(gold=g.D(0), wood=g.D(0), stone=g.D(0), iron=g.D(0))
        game = object.__new__(asc.Game)
        game.r = realm
        allowed = asc.valid_actions(game)
        self.assertNotIn('castle', allowed)
        self.assertIn('wait', allowed)

    def test_action_mask_allows_safe_attack(self):
        realm = g.Realm(soldiers=g.D(1000), threat=g.D(1))
        game = object.__new__(asc.Game)
        game.r = realm
        self.assertIn('attack', asc.valid_actions(game))

    def test_masked_choice_returns_allowed_action(self):
        realm = g.Realm()
        ai = auto.NeuralGovernor()
        allowed = {'wait', 'tax_up'}
        self.assertIn(asc.choose_masked(ai, realm, allowed), allowed)

    def test_province_bonus_stacks_by_category(self):
        state = asc.AscendantState(provinces=['Greenfields', 'Crownlands'])
        self.assertEqual(asc.province_bonus(state, 'food'), g.D('.13'))

    def test_achievement_unlocks(self):
        state = asc.AscendantState()
        realm = g.Realm(victories=g.D(1))
        world = evolved.WorldState()
        asc.check_achievements(state, realm, world)
        self.assertIn('First Blood', state.achievements)

    def test_relation_labels(self):
        self.assertEqual(asc.relation_label(-80), 'Hostile')
        self.assertEqual(asc.relation_label(80), 'Allied')


if __name__ == '__main__':
    unittest.main()
