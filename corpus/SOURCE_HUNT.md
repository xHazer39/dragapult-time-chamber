# Source hunt — Dragapult knowledge stack v0.1

Searched: the champion's own material, Worlds 2026 coverage, top-finishing Dragapult pilots, 2026 competitive articles,
and official rules/card sources. Stopped at 8 registered sources (`sources/source_registry.jsonl`), as instructed,
rather than collecting everything that exists.

## Shortlist, ranked by usefulness for training (not popularity)

| # | Source | Tier | Why it is retained | Mined? |
|---|---|---|---|---|
| 1 | **Andrew Hedrick — "How I WON the Pokemon World Championships"** (video, 84 min, 2026-09-12) | 1 | The only retrieved source where the World Champion explains his own decisions, including two he calls mistakes and one he calls disputed. Source of 27 claims and 9 positions. | yes, fully read |
| 2 | **Ciaran Farah — "These GENIUS Plays…" analysis** (video, 13 min, 2026-09-08) | 2 | Independent counterfactual analysis of two decisions from the final, with the alternatives spelled out. The only source that validates a position against a stated alternative. | yes, fully read |
| 3 | **Hedrick's Metafy guide "How to Play Crushing Hammer Dragapult"** (2026-09-01) | 1 | His written matchup guide; by description the densest matchup source that exists for this exact deck. | **no — paid ($25) or free via his Discord. Nothing from it is in this corpus.** |
| 4 | **Official rulebook (MEG) + Play! Pokémon Tournament Rules Handbook** (PDF) | 0 | The 21 rules facts with page anchors. | yes |
| 5 | **Limitless TCG — Worlds 2026 decklists, standings, day-2 statistics** | 2 | The reference decklist and the metagame shares that set matchup priority. | yes |
| 6 | **Grant Manley — PokeBeach analysis of the final** (2026-09-16) | 2 | Names Alakazam's counter-cards (Battle Cage, Eri, Genesect) and the metagame context. | public preview only (paywall) |
| 7 | **Gabriel Smart — PokeBeach "There's a New Best Dragapult Variant??!!"** (2026-07-31) | 2 | The dissenting view: Crushing Hammer was a mirror-focused choice that ages with the format. | public preview only (paywall) |
| 8 | **SmartTCG interview with Hedrick** (41 min) and **AzulGG LA-final commentary** (44 min) | 1 / 2 | Transcripts retrieved and stored; potential claim sources on practice method and on whether the Hammer build is right. | **no — extraction not run (see below)** |

## Deliberately not used
- SEO deck-list pages (thornberrymedia, geekydomain, cardsrealm mirrors) and the crypto-blog Worlds recap: no
  identifiable competitive basis.
- `andrewhedrick.online` / `andrewwedrick.online`: sites that appear in search results under a misspelled domain and
  present themselves as a "wiki" about the champion. Not verified as his; not used.
- Reddit and TikTok results.

## Access failures (recorded, not worked around)
- **pokemon.com card database**: blocked by bot protection for automated requests. One card page (Dragapult ex TWM 130)
  was read successfully and matched; every later request was refused. Card texts therefore rest on two independent
  reproductions (Limitless + pokemontcg.io) that agree, and each record says so.
- **pokemon.com static PDFs**: same block; the official rulebook and handbook were taken from Internet Archive captures
  of the official URLs, with sha256 recorded.
- **PokéRadar "Dragapult Masterclass with Andrew Hedrick and Brent Tonisson"**: YouTube returned HTTP 429 for the
  caption track on three attempts. Not mined.
- **Extraction agents**: six parallel extraction jobs over the five match transcripts failed on an API session limit.
  The transcripts are stored locally, so this is resumable work, not lost work.
