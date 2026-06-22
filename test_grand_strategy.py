import unittest

import adaptive_core as adaptive
import game_core as g
import grand_strategy_core as grand
import neural_30s


class GrandStrategyTests(unittest.TestCase):
    def test_neural_cadence_remains_thirty_seconds(self):
        self.assertEqual(neural_30s.NEURAL_DECISION_INTERVAL, 30.0)

    def test_food_shortage_selects_food_objective(self):
        game = type('Game', (), {})()
        game.r = g.Realm(food=g.D(1), population=g.D(1000))
        game.adaptive = adaptive.AdaptiveState()
        game.grand = grand.GrandState()
        self.assertEqual(grand.choose_objective(game), 'Secure Food')

    def test_objective_utility_rewards_matching_action(self):
        self.assertGreater(
            grand.objective_utility('Fortify Frontier', 'wall'),
            grand.objective_utility('Fortify Frontier', 'market')
        )

    def test_quartermaster_efficiency_is_capped(self):
        state = grand.GrandState(quartermaster_level=1000)
        self.assertLessEqual(grand.logistics_efficiency(state), g.D('.35'))

    def test_weariness_rises_with_fatigue(self):
        state = grand.GrandState(war_weariness='0')
        adaptive_state = adaptive.AdaptiveState(fatigue='90', supply='20')
        grand.update_weariness(state, adaptive_state, 10)
        self.assertGreater(g.D(state.war_weariness), g.D(0))

    def test_commanders_learn_after_battle(self):
        state = grand.GrandState(last_battle_count=0)
        adaptive_state = adaptive.AdaptiveState(battles_observed=1, supply='80')
        self.assertTrue(grand.learn_commanders(state, adaptive_state))
        self.assertGreater(state.marshal_level, 1)
        self.assertGreater(state.quartermaster_level, 1)


if __name__ == '__main__':
    unittest.main()
