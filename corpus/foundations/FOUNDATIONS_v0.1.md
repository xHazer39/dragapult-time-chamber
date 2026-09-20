# Dragapult Foundations v0.1

Six Concepts and twelve DecisionCases for a player who is still learning both competitive Pokémon TCG and this
Dragapult deck. It sits **alongside** the elite layer, which is unchanged: nothing in `corpus/extracted/`,
`corpus/validated/` or `corpus/sources/` was moved, rewritten or deleted for this.

```
corpus/
├── foundations/            layer: foundation   ← this document
│   ├── concepts.json       6 core Concepts
│   └── decision_cases.jsonl  12 cases, 2 per Concept
└── (everything else)       layer: elite        Hedrick/Farah/Manley claims, 12 candidates,
                            11 advanced DecisionCases, playbook, matchups, source registry
```

Check both layers: `python corpus/check.py`.
Import this layer into the Chamber: `python corpus/import_foundations.py` (idempotent).

## The six Concepts

Five of the six already existed as canonical Chamber concepts, so they are reused rather than duplicated. Only
`setup_and_evolution_engine` is new.

| Concept | Skill | New? | What it is for |
|---|---|---|---|
| `setup_and_evolution_engine` | planning | **new** | Dreepy → Drakloak → Dragapult ex on time, and the draw/search that gets you there |
| `information_before_commitment` | sequencing | reused | Free information first; irreversible actions after |
| `prize_map_t_plus_2` | prize_mapping | reused | This turn's Prizes and next turn's, together |
| `phantom_dive_future_ko_setup` | damage_allocation | reused | Counters that KO nothing now but create Prize value next turn |
| `two_prize_bench_liability` | board_bench_discipline | reused | A benched Pokémon ex is a 2-Prize gust target |
| `resource_preservation` | resource_management | reused | Spend the recoverable, keep the unique |

The names requested in the brief map onto these: `phantom_dive_damage_allocation` → `phantom_dive_future_ko_setup`,
`bench_and_prize_liability` → `two_prize_bench_liability`, `resource_and_energy_preservation` →
`resource_preservation`. Adopting the existing ids avoids a duplicate concept and a second FSRS memory for the
same idea.

## The twelve cases

Each case has exactly one `primary_concept` — the thing it is meant to train — plus at most one secondary link.

| Case | Target concept | Kind | Evidence level that decides | Source |
|---|---|---|---|---|
| `found-setup-first-turn` | setup_and_evolution_engine | A · constructed | **FACT** (LEGALITY, STRICT_DOMINANCE) | rules + card text |
| `found-setup-weak-hand-mirror` | setup_and_evolution_engine | B · pro | UNGRADED (PRO_LINE + HEURISTIC) | Hedrick 0:51:32 |
| `found-info-recon-before-ultra-ball` | information_before_commitment | A · constructed | **FACT** (STRICT_DOMINANCE) | card text |
| `found-info-check-their-answer` | information_before_commitment | B · pro | UNGRADED (PRO_LINE + HEURISTIC) | Hedrick 0:31:54 |
| `found-prize-route-on-their-bench` | prize_map_t_plus_2 | A · constructed | **FACT** (PRIZE_ARITHMETIC) | rules + card text |
| `found-prize-boss-target-final` | prize_map_t_plus_2 | B · pro | UNGRADED (PRO_LINE + HEURISTIC) | Farah 0:07:17 |
| `found-dive-counters-for-next-turn` | phantom_dive_future_ko_setup | A · constructed | **FACT** (PRIZE_ARITHMETIC, EXACT_DAMAGE) | rules + card text |
| `found-dive-hammer-and-counters` | phantom_dive_future_ko_setup | B · pro | UNGRADED (PRO_LINE + HEURISTIC) | Hedrick 0:39:46 |
| `found-bench-meowth-liability` | two_prize_bench_liability | A · constructed | **FACT** (PRIZE_ARITHMETIC, LEGALITY, RULE) | rules + card text |
| `found-bench-fez-active-gusts` | two_prize_bench_liability | B · pro | UNGRADED (PRO_LINE + HEURISTIC) | Hedrick 0:26:07 |
| `found-resource-ultra-ball-discard` | resource_preservation | A · constructed | **FACT** (RESOURCE_ARITHMETIC) | card text + deck list |
| `found-resource-stretcher-timing` | resource_preservation | B · pro | UNGRADED (PRO_LINE + HEURISTIC) | Hedrick 1:04:10 |

**Case A** is a clean, fully stated position whose answer follows from official card text, the rulebook and the
deck list. It is `synthetic: true`, `reconstruction: exact`, and it carries FACT evidence with a named
deterministic basis — one of RULE, LEGALITY, EXACT_DAMAGE, PRIZE_ARITHMETIC, RESOURCE_ARITHMETIC, FORCED_LINE,
STRICT_DOMINANCE. No FACT claim is made without one.

**Case B** is a real position from a Worlds 2026 match, taken from material already in the elite corpus. It is
`synthetic: false`, `reconstruction: medium` or `low`, and it stays **UNGRADED**: a pro's line is what a pro
chose, not a proof. Six of the twelve cases are therefore ungraded on purpose. `PRO_LINE != BEST_MOVE`.

Five Case Bs re-use a position that also exists in the elite layer (`derived_from` names it) with the foundation
concept as the target instead of the elite one. Only the foundation layer is imported into the Chamber, so no
position is ever scheduled twice.

## What is deliberately not imported

- **Research labels** (`BEST`, `EXCELLENT`, `GOOD`, `INACCURACY`, `MISTAKE`, `UNGRADED`). They describe the
  research pass, not the game. They stay in the corpus files and never reach the database. In the Chamber, only
  FACT / COACH_GOLD / CONSENSUS evidence carrying a verdict grades an answer.
- **Secondary links to elite concepts.** The foundation curriculum is exactly six concepts; `import_foundations.py`
  prints each skipped link rather than silently adding a seventh memory to schedule.

## Known limits

- Outside a session (opening a case directly at `#case/<id>`) the Chamber targets the case's first linked concept
  by id, which is not always the `primary_concept` recorded here. Inside a session — the normal path — the
  scheduler's choice is what the rep trains.
- Nothing here has a COACH_GOLD or CONSENSUS row: no qualified reviewer has validated these positions and no two
  independent sources state the same principle precisely enough to group. Not invented.
- The Case A positions are constructed teaching positions. They are correct about the rules and the arithmetic;
  they are not claims about what happens in real games.
