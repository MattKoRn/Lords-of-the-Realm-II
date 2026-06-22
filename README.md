# Endless Realm II: Neural Reign

A persistent, terminal-based medieval realm simulator inspired by the broad strategy loop of **Lords of the Realm II**, with original systems and code.

The entire kingdom is controlled by an evolving neural governor. The player observes, navigates reports, pauses the simulation, dismisses offline progress, and quits. There are no manual economy, construction, taxation, diplomacy, prestige, or combat commands.

## Current features

- Endless progression with algorithmic large-number suffixes
- Fully autonomous workforce, construction, taxation, combat, prestige, and expansion
- Neural action masking that removes impossible choices before selection
- Outcome memory that learns whether recent actions improved the realm
- Utility-shaped neural decisions for famine, morale, military risk, crises, and prestige
- Adaptive exploration, confidence estimates, cooldowns, and anti-repetition penalties
- Persistent seasons, weather, research, technologies, rivals, objectives, and events
- Provinces, achievements, eras, stability, legitimacy, disasters, and diplomacy tiers
- Wonders, trade routes, council doctrine, golden ages, and famine warnings
- Campaign combat with no permanent game-over state
- Flicker-free dismissible offline-progress popup
- Silent realm autosave every second
- Silent neural, world, dynasty, and reign-state saves every five seconds
- Corrupt-save recovery and validation for large-number and world-state data

## Run

### Windows

Double-click `START_GAME.bat`, or run:

```powershell
py -m pip install -r requirements.txt
py run_game.py
```

### Linux or macOS

```bash
python3 run_game.py
```

A terminal around 110 columns by 28 rows provides the best dashboard layout. Smaller terminals remain supported with reduced visible content.

## Observation controls

| Key | Action |
|---|---|
| `1`–`9`, `0`, `-` | Jump to a report tab |
| Left / Right | Change report tab |
| `Tab`, `[` or `]` | Change report page |
| `P` or Space | Pause or resume simulation |
| `Q` | Save and quit |
| Enter / Escape / `D` / Space | Dismiss offline-progress popup |

No key performs a kingdom action. Every consequential decision is made by the neural governor.

## Neural governor

The current governor combines a feed-forward policy network with:

- **Action masking:** unaffordable or invalid actions are excluded.
- **Outcome memory:** each action receives a rolling score based on changes to wealth, happiness, and military power.
- **Context utility:** famine, low morale, disasters, military danger, labour shortages, and prestige readiness shape neural scores.
- **Adaptive exploration:** the network explores early, then gradually favours learned policies.
- **Confidence:** the UI reports the margin between the best and second-best viable decisions.
- **Cooldowns and novelty pressure:** repeated actions become temporarily less attractive.

The neural state continues evolving and is saved independently from realm data.

## World systems

The autonomous world contains:

- Four seasons and dynamic weather
- A technology tree with permanent bonuses
- Rival kingdoms with hostile, unfriendly, neutral, friendly, and allied relations
- Scaled objectives and rewards
- Dynamic events and disasters
- Eight provinces with specialised bonuses
- Eight achievements
- Five wonders
- Temporary trade routes
- Council doctrines and golden ages
- Endless prestige-based era progression

## Save files

Files are stored in:

```text
~/.endless_realm_ii/save.json
~/.endless_realm_ii/world_state_v3.json
~/.endless_realm_ii/ascendant_state_v4.json
~/.endless_realm_ii/neural_brain_v5.json
~/.endless_realm_ii/neural_reign_v5.json
```

Older neural save files remain untouched for compatibility with previous builds.

## Tests

Run the full regression suite with:

```powershell
py -m unittest test_game_core.py test_dynasty_ascendant.py test_neural_reign.py
```

The project uses the Python standard library, plus `windows-curses` on Windows.
