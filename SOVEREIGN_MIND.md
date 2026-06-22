# Sovereign Mind

The current build remains fully neural-controlled and preserves the 30-second decision cadence.

## Neural planning

Each viable action is evaluated through:

1. The neural network's raw policy score.
2. Learned outcome memory from previous actions.
3. Context utility for food, happiness, military risk, disasters, labour, and prestige.
4. A 30-second look-ahead simulation.
5. The active strategic directive.
6. Forecast risk penalties.

The highest combined score becomes the next autonomous action.

## Strategic directives

The governor automatically selects one of six directives:

- Survive
- Prosper
- Fortify
- Expand
- Innovate
- Unify

Directives influence neural utility without replacing the neural decision.

## New simulation systems

- Peasant, burgher, noble, and clergy influence
- Estate influence normalization
- Intelligence reports
- Forecast gain and risk tracking
- Alternative-action rankings
- Deliberation counters
- Forecast success and failure records

## Interface

The lower dashboard displays:

- Current directive
- Forecasted action
- Forecast gain
- Forecast risk
- Forecast review countdown
- Estate influence percentages

## Controls

There are no manual kingdom actions. Controls remain limited to report navigation, pause/resume, popup dismissal, and save/quit.

## Save file

```text
~/.endless_realm_ii/sovereign_mind_v6.json
```

## Tests

```powershell
py -m unittest test_sovereign_mind.py
```
