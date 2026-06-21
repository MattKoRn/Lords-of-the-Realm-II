# Endless Realm II

A persistent, text-based medieval realm-management game for the terminal, inspired by the broad strategy loop of **Lords of the Realm II** while using original systems and code.

## Features

- Endless progression with algorithmically generated large-number suffixes
- World difficulty, enemy power, rewards, buildings, and prestige that scale indefinitely
- Seven top-level tabs with nested sub-tabs
- Economy, workforce assignment, construction, taxation, population, morale, and resource production
- Recruitable soldiers, archers, and knights
- Campaign combat with victories, setbacks, territory gains, loot, and no game-over state
- Manual, dismissible offline-progress popup on launch
- Silent realm autosave every second
- Compact evolutionary neural governor that can play automatically
- Silent neural-network autosave every five seconds
- Persistent dynasty prestige bonuses
- No third-party runtime dependencies on Linux/macOS

## Run

### Windows

```powershell
py -m pip install windows-curses
py run_game.py
```

### Linux or macOS

```bash
python3 run_game.py
```

Use a terminal at least roughly 100 columns wide and 24 rows tall for the best layout.

## Controls

| Key | Action |
|---|---|
| `1`–`7` | Jump to a top-level tab |
| Left / Right | Change top-level tab |
| `Tab`, `[` or `]` | Change sub-tab |
| Up / Down | Select an action |
| Enter | Perform selected action |
| Displayed letter | Perform that action directly |
| `T` | Toggle the neural governor |
| `P` | Prestige the dynasty |
| `Q` | Save and quit |
| Enter / Escape / `D` / Space | Dismiss offline-progress popup |

## Saves

The game stores data in:

```text
~/.endless_realm_ii/save.json
~/.endless_realm_ii/neural_ai.json
```

Realm data is replaced atomically once per second. Neural weights and evolutionary state are replaced atomically once every five seconds.

## Neural governor

The governor is a small feed-forward policy network. It observes resources, population, happiness, military power, threat, and available workers. It chooses from workforce, construction, recruitment, and campaign actions. Every evaluation cycle, successful weights are retained; underperforming weights mutate from the best-known policy. Its generation, score, mutation rate, and latest choice are visible in the **Neural AI** tabs.

This is intentionally lightweight and dependency-free rather than a heavyweight machine-learning framework.
