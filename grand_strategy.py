#!/usr/bin/env python3
from __future__ import annotations

import curses
import time

import adaptive_core as adaptive
import adaptive_launch
import autonomous_mode as auto
import grand_strategy_core as grand
import imperial_mind as imperial
import sovereign_mind as mind
import game_core as g

D = g.D


class Game(adaptive_launch.Game):
    def __init__(self, screen):
        super().__init__(screen)
        self.grand = grand.load_state()
        self.last_grand_save = time.monotonic()
        self.grand_clock = time.monotonic()
        self.last_objective = self.grand.objective
        self.r.log('Grand Strategy systems activated.')

    def strategic_readiness(self):
        base = adaptive.adjusted_readiness(self.adaptive, self.r)
        return base * (D(1) + grand.commander_bonus(self.grand))

    def strategic_actions(self):
        allowed = self.adaptive_actions()
        if D(self.grand.war_weariness) >= D(70):
            allowed.discard('attack')
        return allowed

    def strategic_utility(self, action):
        utility = self.adaptive_utility(action)
        utility += grand.objective_utility(self.grand.objective, action)
        utility += float(grand.commander_bonus(self.grand))
        weariness = D(self.grand.war_weariness)
        if weariness > D(50):
            if action in ('wait', 'farmer', 'tax_down'):
                utility += 1.8
            if action in ('attack', 'knight'):
                utility -= 3.5
        return utility

    def choose_strategic_action(self, allowed):
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
                + self.strategic_utility(action)
                + gain * 2.2
                - risk * 5.0
            )
            scored.append((score, gain, risk, action))
        scored.sort(reverse=True)
        return (scored[0][3], scored) if scored else ('wait', [])

    def ai_action(self):
        try:
            self.sovereign.directive = mind.select_directive(self)
            self.grand.objective = grand.choose_objective(self)
            self.adaptive.formation = adaptive.choose_formation(self.adaptive, self.r)
            self.imperial.recommended_unit = imperial.recommended_counter(self.r)
            self.imperial.battle_readiness = str(self.strategic_readiness())
            self.imperial.expected_loss = str(imperial.estimated_loss_percent(self.r))
            action, ranking = self.choose_strategic_action(self.strategic_actions())

            self.ai.last_action = action
            self.ai.decisions += 1
            self.ai.action_counts[action] += 1
            self.ai.usage_memory[action] += 1
            margin = ranking[0][0] - ranking[1][0] if len(ranking) > 1 else 3.0
            self.ai.confidence = max(0.0, min(1.0, .5 + margin / 6))
            best_score = ranking[0][0] if ranking else 0.0
            best_risk = ranking[0][2] if ranking else 0.0
            self.grand.last_explanation = grand.explanation(self, action, best_score, best_risk)
            self.ai.reason = self.grand.last_explanation
            imperial.record_decision(self.imperial, self, action, ranking)
            auto.execute(self.ai, self.r, action)

            self.forecast_baseline = g.realm_worth(self.r)
            self.forecast_age = 0.0
            self.forecast_pending = True
            self.camera_plan = self.build_camera_plan(action)
            if action == 'attack':
                self.camera_plan = [
                    (0.0, 'Command', 0, 'Neural war council authorises the campaign'),
                    (3.0, 'Military', 0, f'Formation: {self.adaptive.formation}'),
                    (9.0, 'Military', 1, 'Battle casualties and survivors'),
                    (18.0, 'Neural', 0, 'Commanders study the outcome'),
                    (26.0, 'Command', 0, 'War council prepares the next decision'),
                ]
            self.camera_started = time.monotonic()
            self.camera_phase = -1
            self.apply_camera(force=True)
        except (ArithmeticError, ValueError, TypeError, KeyError) as exc:
            self.ai.last_result = f'Grand strategy decision rejected: {exc}'[:160]

    def complete_objective(self):
        if D(self.grand.objective_progress) < D(100):
            return
        completed = self.grand.objective
        self.grand.objectives_completed += 1
        self.r.gold += D(250) * D(self.grand.objectives_completed)
        self.r.renown += D(5)
        self.grand.major_events.append(f'Objective completed: {completed}.')
        self.grand.major_events = self.grand.major_events[-20:]
        self.r.log(f'Grand objective completed: {completed}.')
        self.grand.objective = grand.choose_objective(self)
        self.grand.objective_progress = '0'
        if self.camera_enabled:
            self.focus_camera('Command', 0, f'Objective completed: {completed}', 9.0)

    def update(self):
        now = time.monotonic()
        elapsed = max(0.0, min(1.0, now - self.grand_clock))
        self.grand_clock = now

        original_tick = adaptive.logistics_tick
        adaptive.logistics_tick = lambda state, realm, dt: None
        try:
            super().update()
        finally:
            adaptive.logistics_tick = original_tick

        if not self.paused and elapsed > 0:
            efficiency = grand.logistics_efficiency(self.grand)
            original_tick(self.adaptive, self.r, D(elapsed) * (D(1) - efficiency))
            grand.update_weariness(self.grand, self.adaptive, elapsed)
            self.adaptive.formation = adaptive.choose_formation(self.adaptive, self.r)
            self.imperial.battle_readiness = str(self.strategic_readiness())
            self.grand.objective_progress = str(grand.objective_progress(self))
            self.complete_objective()
            if grand.learn_commanders(self.grand, self.adaptive):
                self.grand.major_events.append('Command staff gained battle experience.')
                self.grand.major_events = self.grand.major_events[-20:]
            if self.grand.objective != self.last_objective:
                self.last_objective = self.grand.objective
                if self.camera_enabled:
                    self.focus_camera('Command', 0, f'New objective: {self.grand.objective}', 8.0)

        if now - self.last_grand_save >= 5:
            grand.save_state(self.grand)
            self.last_grand_save = now

    def draw(self):
        super().draw()
        h, w = self.s.getmaxyx()
        if h < 24 or w < 86:
            return
        tab = self.TABS[self.tab]
        if tab == 'Command':
            row = 20
            self.add(row, 2, 'GRAND STRATEGY', curses.A_BOLD)
            self.add(row + 1, 2, f'Objective: {self.grand.objective}')
            self.add(row + 2, 2, f'Progress: {self.grand.objective_progress}%')
            self.add(row + 3, 2, f'War weariness: {self.grand.war_weariness}%')
            self.add(row + 4, 2, f'Completed objectives: {self.grand.objectives_completed}')
        elif tab == 'Neural':
            row = 26
            self.add(row, 3, 'NEURAL EXPLANATION', curses.A_BOLD)
            self.add(row + 1, 3, self.grand.last_explanation)
            self.add(row + 2, 3, f'Marshal {self.grand.marshal_level} | Quartermaster {self.grand.quartermaster_level} | Strategist {self.grand.strategist_level}')
        status = (
            f' Objective {self.grand.objective} {self.grand.objective_progress}% | '
            f'Weariness {self.grand.war_weariness}% | Marshal {self.grand.marshal_level} '
        )
        self.add(h - 8, 0, status[:w - 1].ljust(w - 1), curses.A_BOLD)
        self.s.refresh()

    def save_all(self):
        super().save_all()
        grand.save_state(self.grand)


def main():
    try:
        curses.wrapper(lambda screen: Game(screen).run())
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
