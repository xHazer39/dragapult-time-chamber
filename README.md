# Dragapult Time Chamber

A local trainer for one thing: stop repeating the high-leverage decision errors you make with your Dragapult ex deck.

It keeps your important decisions (from your own games, pro matches and coach notes) as **DecisionCases**. It links
each case to **Concepts**, makes you commit a plan before you see any feedback, and shows feedback labelled by
evidence level. It schedules concept memory with FSRS, then checks whether the error stops coming back on **unseen**
positions and in **real** games.

## What it is not

It has no rules engine, simulator, card database, AI opponent, best-move predictor, full PTCGL parser or automatic
mistake mining. It needs no accounts, cloud or network. You play real games in Pokémon TCG Live and use TCG Masters,
Dead Draw, PrizeMap, coaches and VODs outside the app. The Chamber only stores links to them.

## Install and launch

```sh
./run                 # first run creates .venv and installs py-fsrs, then opens http://127.0.0.1:8765
./run serve --no-open --port 9000
```

Needs Python 3.11 or newer. The only runtime dependency is `fsrs` (py-fsrs).

## Workflow

1. **Real game / pro source → Inbox.** Paste a PTCGL Battle Log, a coach note, a pro-match reference or an external
   link. It is stored exactly as given, with its SHA-256, and can never be modified or deleted. Logs are grouped by
   `Turn #` headers only. Nothing is judged automatically.
2. **Inbox → CandidateCase.** Tick the relevant log lines and create a candidate. If you entered the opponent's name,
   it is replaced by `OPPONENT` in the excerpt. You then write the observed state yourself: only what you could know at
   decision time. You also set choices and their completeness, unknowns, criticality with its source, concepts and
   evidence.
3. **Validate → DecisionCase.** Promotion refuses anything that breaks an invariant, and gives the reason.
4. **Training.** Today shows only how many reps are recommended — never what they target, because reading "this rep
   is about your spread-damage leak" before deciding would answer the question for you. For each case you lock your
   plan, then decide, then see the evidence ledger, the uncertainty, why the scheduler chose this rep and the
   concepts. Each rep trains **one** target concept, and that is the only concept whose recall you rate and whose
   FSRS memory is rescheduled; the other concepts linked to the case are shown but stay unscheduled.
5. **Transfer.** The scheduler prefers positions you have not seen. In Progress, log real-match opportunities (L4) for a
   concept. The main signal is whether an error recurs after its first occurrence, split by drills and real games.

## Evidence levels

| Level | Meaning | Grades an answer? |
|---|---|---|
| FACT | Deterministic consequence of the stated position. Allowed only when reconstruction is `exact`/`high`. | yes |
| COACH_GOLD | A named reviewer validated it. | yes |
| CONSENSUS | Several independent expert sources agree (references required). | yes |
| PRO_LINE | A strong player chose it. **Not** a best move; cannot carry a verdict. | no |
| SIMULATION | Model/simulator output. | no |
| HEURISTIC | Useful principle, unproven. | no |
| UNKNOWN | Not established. | no |

An answer is graded only when grading-level evidence judges that choice unanimously. Otherwise the app says
"Not graded", and after the reveal you can say whether it was an error (recorded as `self`, kept separate). Evidence is
append-only, and disagreements are displayed, not resolved.

## Memory vs competitive performance

- **Memory (FSRS)** answers "when is this concept worth retrieving again?". The recall probability shown is about
  remembering the concept. It is not playing skill.
- **Performance** is counts with denominators: seen (L0–L1), unseen (L2–L3), real games (L4), repeat errors after the
  first error, and median decision time. Below the minimum sample sizes the app says *insufficient evidence*.

## Optional GLM coach

```sh
export OPENROUTER_API_KEY=...          # server-side only, never sent to the browser
export CHAMBER_COACH=1
export CHAMBER_COACH_MODEL=z-ai/glm-5.3-flash   # default
./run
```

The coach receives only structured case context: position, plan, choice and evidence. It never gets raw logs or the
full record. Its output is labelled as not being evidence. Any new strategic claim is listed as unverified and is never
merged into the evidence. Without a key, offline, or on a malformed reply, the coach simply reports "unavailable".

## Data

- Database: `~/.local/share/dragapult-time-chamber/chamber.db` (`$XDG_DATA_HOME` is respected; override with
  `CHAMBER_DB=/path/file.db` or `--db`).
- Backup, safe while the app runs: `./run backup ~/chamber-backup-$(date +%F).db`
- On first start with an empty DB, demo content is loaded. All demo cases are marked `synthetic`, and their strategy is
  HEURISTIC at most.

## Deck versions

Deck lists are immutable. The hash covers the exact 60-card list, so a one-card change gives a new version:

```sh
./run deck-add my_list.txt --source "list I registered for X" --format "Standard" --date 2026-09
```

`my_list.txt` is a PTCGL export (`3 Dragapult ex TWM 130` per line). Cases record the deck version they were written
for. Today warns when active cases belong to an older version. Concepts carry across versions.

## Tests

```sh
.venv/bin/pip install -r requirements-dev.txt && .venv/bin/python -m playwright install chromium
.venv/bin/python -m pytest
```

Tests use temporary databases only, and a local fake server stands in for the LLM.
