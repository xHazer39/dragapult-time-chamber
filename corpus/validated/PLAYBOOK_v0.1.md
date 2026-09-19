# Dragapult playbook v0.1

**14** principles extracted from the sources in `sources/source_registry.jsonl`, grouped into the 13 Concepts in
`extracted/concepts.json` (principles 1 and 2 are both about the Budew lock war). Every one is **HEURISTIC**:
an elite player or analyst said it, in a stated context. None of it is proven, and none of it grades a move by itself.
Claim ids in brackets point to `extracted/claims.jsonl`, where each has a verbatim quote and a timestamp.

Deck: Hedrick's Worlds 2026 list (`decks/hedrick_worlds_2026.json`), which is the same list, card for card, that
Gaetano is learning. Card texts and rules used below are in `facts/`.

## Early game

1. **Win the Budew lock war (mirror).** The opening exchange is about which Budew survives. A third Darkness Energy
   makes Munkidori available early to heal your own Budew, so you can Knock Out theirs with Itchy Pollen.
   [claim_eeHvbC8bpXQ_8, _7]
2. **Going first in the mirror, Risky Ruins punishes their Budew.** Bench, then end the turn with Risky Ruins:
   a benched Budew takes 20, so your own Budew can then Knock it Out. [claim_eeHvbC8bpXQ_14]
3. **Do not be the first to engage with an underdeveloped board.** Attacking early gives them the Crushing Hammer and
   Unfair Stamp comeback window. [claim_eeHvbC8bpXQ_9, _2]
4. **But attack when they cannot answer with a Knock Out.** Against Zoroark in particular, if they have no Energy and no
   revenge Knock Out, the aggressive Phantom Dive is the way to win. [claim_eeHvbC8bpXQ_11, _26; claim_OcmjWWv-daQ_30]
   *Principles 3 and 4 constrain each other; the sources give no rule for the boundary. Open question.*

## Reading the opponent

5. **Read their hand by what they did not play.** If they would have played a card, and did not, they probably do not
   have it. Track their exact hand size and everything they searched. [claim_OcmjWWv-daQ_28, _29]
6. **Count their outs before choosing a disruption.** How much Energy is left in their deck, how many Boss's Orders have
   they used, what is likely prized. Check them for the resource they are least likely to find.
   [claim_eeHvbC8bpXQ_20, _19, _18]

## Damage and targets

7. **The Risky Ruins + Dunsparce + Munkidori loop.** Benching a Basic non-Darkness Pokémon under your own Risky Ruins
   puts 20 damage on it; Munkidori moves up to 3 counters onto their board each turn, with no attack needed.
   [claim_eeHvbC8bpXQ_1, _3, _10]
8. **Pick the target that denies their next turn.** Not the biggest number and not the easiest Prize: the piece their
   next turn depends on. In the Bronzong/Lopunny game, Hedrick says Knocking Out the Bronzong would have been the worst
   of three options, and Knocking Out Dusclops kept both his Drakloak and his Fezandipiti ex alive.
   [claim_eeHvbC8bpXQ_15, _16, _17]
9. **Do not feed their draw engine.** A Knock Out that triggers Flip the Script, or that leaves their draw Pokémon
   alive, can cost more than the Prize is worth. [claim_OcmjWWv-daQ_31; claim_eeHvbC8bpXQ_25]
10. **Check their counter-line first.** Play out their Munkidori moves, their gust and their revenge Knock Out. If their
    answer leaves you without an attacker, the aggressive line is wrong. [claim_eeHvbC8bpXQ_12]

## Resources and tempo

11. **Recover a resource before it can be denied.** Hedrick names not playing Night Stretcher one turn earlier, to put a
    Darkness Energy back in hand before a third Crushing Hammer, as the mistake that cost him a game.
    [claim_eeHvbC8bpXQ_21]
12. **Know which cards are consistency and which are resources.** Three Night Stretcher is a consistency card you spend;
    two is a resource you ration. Ultra Ball is weaker in the mirror (item lock, big hands) and much more needed
    elsewhere. [claim_eeHvbC8bpXQ_4, _5, _6]
13. **A damaged Dragapult does not have to keep attacking.** Retreat it, keep Budew locking and move damage with
    Munkidori: the opponent who attacked into your Dragapult should regret it. [claim_eeHvbC8bpXQ_13, _23]

## Prize mapping

14. **Prefer the line that threatens to win next turn.** Between two attacking lines, the one that forces them to answer
    is usually worth more than the extra Prize that threatens nothing. Hedrick's own example is a position he judges he
    played wrong. [claim_eeHvbC8bpXQ_22]

## What this playbook does not contain

- Hedrick's written matchup guide (Metafy, paid) was not read. It is the biggest single gap.
- No prize-map arithmetic ("what wins in two turns from here") from any source; only case-by-case reasoning.
- Nothing on the Crustle, Basic Box, Slowking or Mega Excadrill matchups beyond one sentence each.
