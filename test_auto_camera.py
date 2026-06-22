import unittest

import auto_camera


class AutoCameraTests(unittest.TestCase):
    def test_attack_routes_to_military_details(self):
        tab, subtab, _ = auto_camera.ACTION_VIEWS['attack']
        self.assertEqual(tab, 'Military')
        self.assertEqual(subtab, 1)

    def test_prestige_routes_to_legacy(self):
        tab, subtab, _ = auto_camera.ACTION_VIEWS['prestige']
        self.assertEqual((tab, subtab), ('Legacy', 0))

    def test_plan_spans_full_decision_window(self):
        game = object.__new__(auto_camera.Game)
        plan = game.build_camera_plan('market')
        self.assertEqual(plan[0][0], 0.0)
        self.assertEqual(plan[-1][0], 27.0)
        self.assertEqual(plan[1][1], 'Economy')


if __name__ == '__main__':
    unittest.main()
