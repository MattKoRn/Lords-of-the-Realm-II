# Imperial Mind

Imperial Mind is the current fully autonomous build of Endless Realm II.

## Neural cadence

The governor still makes one consequential kingdom decision every 30 seconds.

## Composition-aware military planning

The governor now evaluates the estimated enemy composition and recommends a counter unit:

- Soldiers counter Knights
- Archers counter Soldiers
- Knights counter Archers

Attack permission also considers:

- Army readiness compared with the enemy
- Estimated friendly casualties
- Active disasters
- Existing action-mask rules

## Autonomous policies

Every three minutes, the neural government selects a strategic policy:

- Balanced Realm
- Emergency Rations
- Public Works
- War Economy
- Open Markets
- Royal Academy

Policies apply automatic economic, research, or military modifiers. They influence neural utility but do not add player decisions.

## Improved neural scoring

Each viable action combines:

- Neural policy output
- Learned outcome memory
- Survival context
- Strategic directive
- Enemy-composition utility
- Current autonomous policy
- 30-second look-ahead gain
- Forecast risk

## Auto camera

The camera still toggles with `C`.

Campaign decisions receive a dedicated sequence:

1. Command authorisation
2. Army composition
3. Battle report
4. Neural consequences
5. Return to Command

Other actions continue to route to their relevant report and detail page.

## UI

The Neural report now includes:

- Current imperial policy
- Counter-unit recommendation
- Battle readiness
- Expected casualties
- Latest strategic choice

The Military report includes enemy composition and the neural counter recommendation.

## Save file

```text
~/.endless_realm_ii/imperial_mind_v7.json
```

## Tests

```powershell
py -m unittest test_imperial_mind.py
```
