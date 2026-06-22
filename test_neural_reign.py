import unittest

import autonomous_mode as auto
import dynasty_ascendant as asc
import game_core as g
import kingdom_evolved as evolved
import neural_reign as reign


class NeuralReignTests(unittest.TestCase):
    def test_brain_tracks_outcome_memory(self):
        ai = reign.CognitiveGovernor()
        realm = g.Realm()
        ai.last_action = 'farmer'
        ai.last_worth = str(g.realm_worth(realm))
        ai.last_happiness = str(realm.happiness)
        ai.last_power = str(realm.military_power())
        realm.gold += g.D(1000)
        ai.observe_outcome(realm)
        self.assertGreaterEqual(ai.outcome_memory['farmer'], 0)

    def test_cognitive_choice_respects_allowed_actions(self):
        ai = reign.CognitiveGovernor()
        game = object.__new__(reign.Game)
        game.r = g.Realm()
        game.asc = asc.AscendantState()
        action = ai.choose_cognitive(game, {'wait', 'tax_up'})
        self.assertIn(action, {'wait', 'tax_up'})

    def test_famine_bias_prefers_food_actions(self):
        ai = reign.CognitiveGovernor()
        game = object.__new__(reign.Game)
        game.r = g.Realm(food=g.D(1), population=g.D(1000))
        game.asc = asc.AscendantState()
        farmer = ai.context_utility(game, 'farmer')
        attack = ai.context_utility(game, 'attack')
        self.assertGreater(farmer, attack)

    def test_wonder_unlock(self):
        state = reign.ReignState()
        realm = g.Realm(population=g.D(1000))
        world = evolved.WorldState()
        reign.update_wonders(state, realm, world)
        self.assertIn('Grand Granary', state.wonders)

    def test_wonder_bonus(self):
        state = reign.ReignState(wonders=['Grand Granary', 'Hall of Kings'])
        self.assertEqual(reign.wonder_bonus(state, 'food'), g.D('.20'))

    def test_trade_route_produces_income(self):
        state = reign.ReignState(trade_routes=[{'good': 'Grain', 'yield': '100', 'age': 0.0}])
        realm = g.Realm()
        world = evolved.WorldState()
        gold_before = realm.gold
        food_before = realm.food
        reign.update_trade(state, realm, world, 1.0)
        self.assertGreater(realm.gold, gold_before)
        self.assertGreater(realm.food, food_before)

    def test_manual_selected_action_remains_disabled(self):
        self.assertIsNone(auto.Game.selected_action(object()))


if __name__ == '__main__':
    unittest.main()
