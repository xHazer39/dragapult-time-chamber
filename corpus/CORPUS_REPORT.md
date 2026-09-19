# Dragapult knowledge stack v0.1 — corpus report

Research only. No application code, no database write, no change to the Chamber.

## 1. Deck status

- `decks/current_dragapult.json` — the list Gaetano is learning, as he stated it on 2026-09-19 (second, corrected
  version). **Counts verified, prints partial.** By name and count it is identical to the reference list
  (both hash `38bfd811b4a3f8b6` over sorted "count name" lines).
- `decks/hedrick_worlds_2026.json` — Andrew Hedrick's 1st-place list, from the Limitless tournament decklist
  (`/decks/list/28752`). Kept separate; never merged.
- Unverified in the current deck: the ASC Dragapult ex number, the Unfair Stamp number, the MEE/Perfect Order Poké Pad
  number, and whether Dunsparce / Meowth ex / Fezandipiti ex are the English prints. Prints do not change card text,
  so they do not affect training.
- The Chamber's seeded deck v1 (`4fe582e25a26866f`) has the same names and counts with different prints.

## 2. Sources retained

See `SOURCE_HUNT.md` for the ranked shortlist and the reasons. Eight registered; two fully mined (Hedrick's own
84-minute video, Farah's 13-minute analysis); official rulebook and tournament handbook mined for rules; Limitless for
the list and the metagame. The champion's own written guide is **paid and was not read**.

## 3. Concepts

Concepts: **13**, in `extracted/concepts.json`, each with supporting claim ids: budew_lock_war, delay_engagement_until_ready,
risky_ruins_damage_loop, attack_when_no_response_ko, check_opponent_counterplay, target_selection_by_denial,
read_hand_by_omission, count_opponent_outs, preempt_resource_denial, threaten_win_next_turn, rotate_damaged_dragapult,
resource_count_discipline, avoid_feeding_opponent_draw. Human version: `validated/PLAYBOOK_v0.1.md`.

## 4. Matches

Pro matches: **6** registered in `sources/pro_matches.jsonl`: Worlds final (Hedrick–Cassiraga), Worlds top 4 (Hedrick–Tonisson),
Worlds R11 (Hedrick–Koyama), LA Regionals final and top 4, and the PokéRadar top-4 "Masterclass" (captions not
retrievable). Transcripts with timestamps are stored for five of them.

## 5–6. Counts

- Claims: **37**, every video quote machine-verified as an exact substring of the caption line at its timestamp.
- Candidate positions: **12** (target was 30–40 — see §9).
- Chamber-ready DecisionCases: **11** (target was 15–20).
- Rules facts: **23**. Card facts: **24** (every distinct card in the deck).
- Playbook principles: **14** (`validated/PLAYBOOK_v0.1.md`), grouped into the 13 Concepts.
- Registered sources: **8** (`sources/source_registry.jsonl`).

`python corpus/check.py` re-verifies every count above, and every id/claim/source/deck reference, against the files.

## 7. Evidence breakdown

| Level | Count | Where |
|---|---|---|
| FACT | 48 | 23 rules (page-anchored to the official PDFs) + 24 card records + 1 metagame statistic |
| COACH_GOLD | **0** | No qualified reviewer validated any position. Not invented. |
| CONSENSUS | **0** | No principle was independently stated by two strong sources with enough precision to group |
| PRO_LINE | 23 | 12 candidates + 11 case evidence rows: what the champion actually played |
| SIMULATION | 0 | none used |
| HEURISTIC | 50 in cases + 36 claims | all strategy, from Hedrick, Farah, Manley, Smart |
| UNKNOWN | 17 | explicit uncertainty rows on the cases |

Research labels on the 11 cases: 1 BEST, 1 EXCELLENT, 2 GOOD, 1 INACCURACY, 1 MISTAKE, **5 UNGRADED**. No BRILLIANT,
no GREAT: nothing met the bar. Every label carries a confidence (1 MEDIUM-graded BEST, rest LOW/MEDIUM) and a "why".

## 8. Matchup coverage

`validated/matchups/`: dragapult_mirror, alakazam, zoroark, bronzong_lopunny. Priority follows the Worlds day-2 shares
(Dragapult 29.37%, Alakazam 11.19%, Zoroark 8.39%). Zoroark has claims but no position yet.

## 9. Unresolved questions

1. **When to engage.** "Do not attack with an underdeveloped board" and "attack when they cannot answer" constrain each
   other and no source gives the boundary.
2. **The missed win in game 1 of the final.** Farah asserts it exists and does not state it.
3. **Hedrick's deck-out line in game 2 of the final** — he himself is unsure it was right.
4. **Prize-map arithmetic** for the mirror is absent from every source read.
5. **Regulation H rotation** for the 2027 season was not found in official sources; if H rotates, Dragapult ex TWM 130
   leaves Standard and much of this corpus becomes historical.
6. Whether Boss's Orders MEG 114 prints "Switch in … to the Active Spot" or the older wording: the two databases differ
   and the official page could not be read.

## 10. Cases still UNGRADED, and why

`pro-r4-attack-or-boss` (only the player's own account, hand approximate), `pro-final-deckout-or-redcard` (disputed by
the player himself), `pro-r8-poffin-recovery`, `pro-r8-double-budew`, `pro-r9-budew-recovery` (described as what
happened, with no comparison to an alternative anywhere in the source), plus `cand_OcmjWWv-daQ_9` which never became a
case because the source gives no board. This is the intended outcome: an unvalidated pro line stays UNGRADED.

## 11. Files created

```
corpus/decks/{current_dragapult,hedrick_worlds_2026}.json
corpus/facts/{rules,cards}.jsonl
corpus/sources/{source_registry,pro_matches}.jsonl        corpus/sources/official/   (empty: PDFs kept outside git, hashes recorded)
corpus/extracted/{claims.jsonl,concepts.json,candidate_cases.jsonl}
corpus/validated/{PLAYBOOK_v0.1.md,validation_ledger.jsonl,decision_cases.jsonl}
corpus/validated/matchups/{dragapult_mirror,alakazam,zoroark,bronzong_lopunny}.md
corpus/{SOURCE_HUNT.md,CORPUS_REPORT.md}
```

Transcripts and PDFs live in the session scratchpad, not in git: `…/scratchpad/corpus/` (yt/*.txt, *.pdf).
Their URLs and sha256 are recorded in the corpus so they can be re-fetched.

## 12. Shortfall against the targets, and why

Candidates 12 of 30–40 and cases 11 of 15–20. Six parallel extraction agents over the five stored match transcripts
(≈50,000 words) failed on an API session limit, so only the two sources I read myself were mined. Resuming is cheap:
the transcripts, the extraction brief (`scratchpad/corpus/AGENT_BRIEF.md`) and the quote verifier
(`scratchpad/corpus/verify.py`) are all in place.

## 13. Next action

Buy or obtain (via his Discord) **Hedrick's Metafy guide** and mine it: it is the one source that would add matchup
plans for every deck at once, and it is the only Tier-1 source currently missing.
