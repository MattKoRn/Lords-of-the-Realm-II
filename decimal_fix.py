import sovereign_mind as mind
import game_core as g


def safe_update_estates(state, game, dt):
    r = game.r
    dt = g.D(dt)
    p = g.D(state.peasants_influence)
    b = g.D(state.burghers_influence)
    n = g.D(state.nobles_influence)
    c = g.D(state.clergy_influence)
    p += (r.happiness - g.D(50)) * g.D('.0004') * dt
    b += g.D(g.decimal_log_feature(r.gold + g.D(1))) * g.D('.004') * dt
    n += g.D(g.decimal_log_feature(r.military_power() + g.D(1))) * g.D('.003') * dt
    c += (g.D(100) - abs(r.happiness - g.D(65))) * g.D('.00008') * dt
    state.peasants_influence = str(max(g.D(1), p))
    state.burghers_influence = str(max(g.D(1), b))
    state.nobles_influence = str(max(g.D(1), n))
    state.clergy_influence = str(max(g.D(1), c))
    mind.normalize_estates(state)


mind.update_estates = safe_update_estates
