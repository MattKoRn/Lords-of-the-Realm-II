import unittest
import autonomous_mode as auto
import dynasty_ascendant as asc
import game_core as g
import neural_30s
import sovereign_mind as mind

class SovereignMindTests(unittest.TestCase):
    def test_cadence(self):
        self.assertEqual(neural_30s.NEURAL_DECISION_INTERVAL, 30.0)

    def test_estates_normalize(self):
        state = mind.SovereignState(
            peasants_influence='10', burghers_influence='10',
            nobles_influence='10', clergy_influence='10')
        mind.normalize_estates(state)
        total = sum(mind.estate_values(state).values(), g.D(0))
        self.assertEqual(total.quantize(g.D('.01')), g.D('100.00'))

    def test_food_crisis_directive(self):
        game = object.__new__(mind.Game)
        game.r = g.Realm(food=g.D(1), population=g.D(1000))
        game.asc = asc.AscendantState()
        game.world = object()
        self.assertEqual(mind.select_directive(game), 'Survive')

    def test_no_manual_action(self):
        self.assertIsNone(auto.Game.selected_action(object()))

if __name__ == '__main__':
    unittest.main()
