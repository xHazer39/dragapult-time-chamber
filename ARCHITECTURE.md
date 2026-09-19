# Architecture

Python stdlib HTTP server + SQLite + vanilla JS. One runtime dependency: `fsrs`.

```
chamber/
  db.py         schema; invariants SQLite can enforce (CHECKs, append-only/immutable triggers)
  core.py       decks, raw sources, candidates, validation, promotion, player view, evidence
  train.py      sessions, attempts, grading, FSRS concept reviews, real-game (L4) logging
  stats.py      per-concept performance counts, repeat errors, status labels
  scheduler.py  exploit/coverage/probe plan, "go play" recommendation
  coach.py      optional OpenRouter GLM coach, strict JSON, degrades to "unavailable"
  server.py     JSON routes + static files, one DB connection per request
  static/       index.html, app.js (render only), app.css
  seed.json     demo deck (the user's list) + synthetic demo cases
```

## Core model

RawSource → CandidateCase (untrusted JSON draft) → DecisionCase (explicit columns) ↔ Concept (many-to-many), with
Evidence rows per case. An Attempt links to a case (or to none, for L4) and to per-concept recall rows. A Session holds
a stored plan. Deck versions are keyed by content hash.

## Invariants and where they are enforced

| Invariant | Enforced by |
|---|---|
| Raw sources are never modified or deleted | DB triggers |
| Deck versions are immutable; one card changed = new hash | DB trigger + `deck_hash` |
| Evidence is append-only; disagreement is kept | DB triggers; `disputes()` shows conflicts |
| PRO_LINE / SIMULATION / UNKNOWN never carry a verdict | DB CHECK + validation |
| COACH_GOLD names a reviewer; CONSENSUS cites sources | DB CHECK + validation |
| FACT only on `exact`/`high` reconstruction | DB trigger + validation |
| Only FACT/COACH_GOLD/CONSENSUS grade, and only when unanimous | `train.grade` |
| Nothing from full record, evidence, concepts or hint before answering | `core.player_view` whitelist; session items omit the concept |
| Plan is locked before the decision and cannot change | no update route; `start_attempt` checks required fields |
| An answer cannot change after the reveal | `train.answer` |
| Self-reported outcome never overrides graded evidence | `train.review` |
| FSRS = concept memory only; retries never update it | `train.review`, labels in UI |
| LLM output is never evidence | `coach.ask` returns display-only data; nothing writes it to `evidence` |

## FSRS rating mapping (V1)

The player rates recall of each linked concept after the reveal (Again, Hard, Good or Easy). A hint caps the rating at
Hard. Latency, correctness and retries do not change the rating; they are stored separately. A retry (the same case
within 12 hours) does not update FSRS. The scheduler uses default parameters with fuzzing off. `concept_reviews.log`
keeps every ReviewLog for a future optimizer run once real history exists.

## Scheduler

For each rep, the mode is the one furthest below its share of `CONFIG['mix']`. The order is deterministic.

- **exploit**: concepts with errors in their last 5 graded results, ranked by error rate, repeat errors in real
  games, memory due and criticality.
- **coverage**: other concepts, memory due or never reviewed first, then criticality, with a bonus for skills not yet
  in the plan.
- **probe**: never-attempted cases of concepts with the fewest unseen results.

Within a concept, the chosen case is the first by: unseen, then criticality, then grading-level evidence, then least
recently seen, then a seeded hash. Cases with criticality 0–1 and retired cases are never served. When drills look
strong but no real game has been logged recently, Today recommends going to play.

## Deviations from the brief

- Correctness also has a self-reported outcome (`outcome_source = 'self'`) for ungraded cases. Without it, repeat-error
  tracking would be empty on HEURISTIC-only cases. It is always labelled and never overrides evidence.
- Per-concept error attribution is collected: a multi-concept error counts only against concepts named as causal.
- Case edits after promotion are not supported. Add evidence (append-only) instead, or promote a new case.
- The `stale` status exists, but deck changes do not set it automatically. Today warns instead.

## Hardening invariants

- Self-reported outcomes are weak evidence: they are shown separately from evidence-backed outcomes and cannot certify transfer.
- Multi-concept errors are attributed only to concepts explicitly selected as causal; uncertainty stays unattributed.
- A high-priority leak may receive several different reps in one session, capped and non-consecutive when alternatives exist.
- Exact concept identity is not sent in Today/session payloads before the case reveal. Neither is the scheduler's
  mode or reason, nor any leak detail: Today is neutral, and all of it arrives with the reveal (leaks live in Progress).
- One rep trains one concept. The scheduler's choice is stored on the attempt as `target_concept_id`, and it is the
  only concept whose FSRS memory that rep reviews. Other concepts on the case stay linked for the reveal and for
  root-cause attribution.
