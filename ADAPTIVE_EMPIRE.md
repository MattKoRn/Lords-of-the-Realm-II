# Adaptive Empire

Adaptive Empire is the current fully autonomous build of Endless Realm II.

## Neural control

The neural governor remains the only system allowed to make kingdom decisions. The decision interval remains 30 seconds.

Each action now considers:

- Neural policy output
- Learned outcome memory
- Strategic directive
- Imperial policy
- Enemy composition
- Army supply
- Army fatigue
- Veteran experience
- Formation suitability
- 30-second forecast gain and risk

## Army logistics

Soldiers, archers, and knights consume food and iron over time. Adequate resources restore supply, while shortages reduce it.

Low supply:

- Reduces adjusted battle readiness
- Encourages food and mining actions
- Discourages knights and attacks
- Can force the Orderly Retreat formation

## Fatigue

Battles increase fatigue according to casualties. Fatigue recovers gradually, with faster recovery while supply is healthy.

High fatigue suppresses attacks and increases the neural value of waiting, farming, and reducing taxes.

## Veterancy

Surviving units gain experience after battles. Experience is tracked separately for soldiers, archers, and knights.

Veterancy contributes to adjusted battle readiness and is capped to prevent runaway scaling.

## Formations

The neural military planner automatically chooses:

- Balanced Line
- Shield Wall
- Arrow Screen
- Cavalry Hammer
- Orderly Retreat

Formation selection considers enemy composition, supply, fatigue, and readiness.

## Auto camera

The camera remains toggleable with `C`.

It now gives priority to:

- New disasters
- Policy changes
- Battle aftermath
- Formation selection
- Casualty reports
- Neural after-action learning

These are view changes only and never affect gameplay decisions.

## UI

The Military report now includes formation, supply, fatigue, and veterancy.

The Neural report includes battle observations, total units lost, total enemies defeated, and the latest after-action lesson.

All visible values remain whole numbers and the atomic curses renderer remains active.

## Save file

```text
~/.endless_realm_ii/adaptive_empire_v8.json
```

## Tests

```powershell
py -m unittest test_adaptive_empire.py
```
