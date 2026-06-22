#!/usr/bin/env python3
from __future__ import annotations

import curses
import time

import adaptive_core as core
import autonomous_mode as auto
import imperial_mind as imperial
import sovereign_mind as mind
import game_core as g

D = g.D


class Game(imperial.Game):
    def __init__(self, screen):
        super().__init__(screen)
        self.adaptive = core.load_state()
        self.last_adaptive_save = time.monotonic()
        self.last_disaster = self.asc.disaster
        self.last_policy = self.imperial.policy
        self.r.log('Adaptive Empire systems activated.')

    def adaptive_actions(self):
        allowed = imperial.improved_actions(self)
        readiness = core.adjusted_readiness(self.adaptive, self.r)
        if readiness < D(95) or D(self.adaptive.fatigue) > D(65) or D(self.adaptive.supply) < D(30):
            allowed.discard('attack')
        return allowed

    def adaptive_utility(self, action):
        utility = imperial.composition_utility(self, action)
        fatigue = D(self.adaptive.fatigue)
        supply = D(self.adaptive.supply)
        if fatigue > D(55):
            if action in ('wait', 'farmer', 'tax_down'):
                utility += 2.2
            if action == 'attack':
                utility -= 5.0
        if supply < D(40):
            if action in ('farmer', 'farm', 'miner', 'mine'):
                utility += 1.8
            if action in ('knight', 'attack'):
                utility -= 2.5
        if action == self.imperial.recommended_unit:
            utility += 1.1
        return utility

    def choose_action(self, allowed):
        raw = mind.neural_scores(self.ai, self.r)
        scored = []
        for index, action in enumerate(self.ai.ACTIONS):
            if action not in allowed:
                continue
            gain, risk = mind.simulate_action(self, action)
            score = (
                raw[index]
                + self.ai.context_utility(self, action)
                + mind.directive_bonus(self.sovereign.directive, action)
                + self.adaptive_utility(action)
                + gain * 2.1
                - risk * 4.8
            )
            scored.append((score, gain, risk, action))
        scored.sort(reverse=True)
        return (scored[0][3], scored) if scored else ('wait', [])

    def ai_action(self):
        try:
            self.sovereign.directive = mind.select_directive(self)
            self.adaptive.formation = core.choose_formation(self.adaptive, self.r)
            self.imperial.recommended_unit = imperial.recommended_counter(self.r)
            self.imperial.battle_readiness = str(core.adjusted_readiness(self.adaptive, self.r))
            self.imperial.expected_loss = str(imperial.estimated_loss_percent(self.r))
            action, ranking = self.choose_action(self.adaptive_actions())

            self.ai.last_action = action
            self.ai.decisions += 1
            self.ai.action_counts[action] += 1
            self.ai.usage_memory[action] += 1
            margin = ranking[0][0] - ranking[1][0] if len(ranking) > 1 else 3.0
            self.ai.confidence = max(0.0, min(1.0, .5 + margin / 6))
            self.ai.reason = (
                f'{self.adaptive.formation}; supply {self.adaptive.supply}%; '
                f'fatigue {self.adaptive.fatigue}%.'
            )
            imperial.record_decision(self.imperial, self, action, ranking)
            auto.execute(self.ai, self.r, action)
            self.forecast_baseline = g.realm_worth(self.r)
            self.forecast_age = 0.0
            self.forecast_pending = True

            self.camera_plan = self.build_camera_plan(action)
            if action == 'attack':
                self.camera_plan = [
                    (0.0, 'Command', 0, 'Neural campaign decision'),
                    (3.0, 'Military', 0, f'Formation: {self.adaptive.formation}'),
                    (9.0, 'Military', 1, 'Battle casualties and survivors'),
                    (19.0, 'Neural', 0, 'Learning from battle outcomes'),
                    (27.0, 'Command', 0, 'Recovery and next deliberation'),
                ]
            self.camera_started = time.monotonic()
            self.camera_phase = -1
            self.apply_camera(force=True)
        except (ArithmeticError, ValueError, TypeError, KeyError) as exc:
            self.ai.last_result = f'Adaptive decision rejected: {exc}'[:160]

    def focus_camera(self, tab, subtab, caption, duration):
        if not self.camera_enabled:
            return
        self.camera_plan = [
            (0.0, tab, subtab, caption),
            (duration, 'Command', 0, 'Returning to neural command'),
        ]
        self.camera_started = time.monotonic()
        self.camera_phase = -1
        self.apply_camera(force=True)

    def update(self):
        started = time.monotonic()
        super().update()
        now = time.monotonic()
        dt = max(0.0, min(1.0, now - started))
        if not self.paused:
            core.logistics_tick(self.adaptive, self.r, dt)
            self.adaptive.formation = core.choose_formation(self.adaptive, self.r)
            self.imperial.battle_readiness = str(core.adjusted_readiness(self.adaptive, self.r))
            if core.learn_from_last_battle(self.adaptive, self.r):
                self.focus_camera('Military', 1, self.adaptive.last_lesson, 14.0)
            if self.asc.disaster and self.asc.disaster != self.last_disaster:
                self.focus_camera('World', 0, f'Crisis: {self.asc.disaster}', 10.0)
            if self.imperial.policy != self.last_policy:
                self.focus_camera('Neural', 0, f'Policy changed: {self.imperial.policy}', 9.0)
            self.last_disaster = self.asc.disaster
            self.last_policy = self.imperial.policy
        if now - self.last_adaptive_save >= 5:
            core.save_state(self.adaptive)
            self.last_adaptive_save = now

    def draw(self):
        super().draw()
        h, w = self.s.getmaxyx()
        if h < 22 or w < 82:
            return
        tab = self.TABS[self.tab]
        if tab == 'Military' and self.sub == 0:
            row = 19
            self.add(row, 2, 'ARMY CONDITION', curses.A_BOLD)
            self.add(row + 1, 2, f'Formation: {self.adaptive.formation}')
            self.add(row + 2, 2, f'Supply: {self.adaptive.supply}% | Fatigue: {self.adaptive.fatigue}%')
            self.add(row + 3, 2, f'Veterancy bonus: {core.average_veterancy(self.adaptive, self.r)}%')
        elif tab == 'Neural':
            row = 22
            self.add(row, 3, 'AFTER-ACTION LEARNING', curses.A_BOLD)
            self.add(row + 1, 3, f'Battles observed: {self.adaptive.battles_observed}')
            self.add(row + 2, 3, f'Units lost: {self.adaptive.units_lost} | Defeated: {self.adaptive.units_defeated}')
            self.add(row + 3, 3, f'Last lesson: {self.adaptive.last_lesson}')
        status = (
            f' Formation {self.adaptive.formation} | Supply {self.adaptive.supply}% | '
            f'Fatigue {self.adaptive.fatigue}% | Veterans {core.average_veterancy(self.adaptive, self.r)}% '
        )
        self.add(h - 7, 0, status[:w - 1].ljust(w - 1), curses.A_BOLD)
        self.s.refresh()

    def save_all(self):
        super().save_all()
        core.save_state(self.adaptive)


def main():
    try:
        curses.wrapper(lambda screen: Game(screen).run())
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
