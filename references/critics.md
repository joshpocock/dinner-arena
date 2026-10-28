# The ten critics

Each critic votes on one rule, computed by `scripts/arena.py`. If the two places are equal on that
rule (or the data is missing), the critic abstains. You only write the line; the vote is fixed.

| # | Critic | Votes for | Voice |
|---|---|---|---|
| 1 | The Budget Executioner | the lower price level | Treats every dollar like a hostage. "Price level one. The other one wants a mortgage." |
| 2 | The Distance Hater | the shorter distance | Refuses to cross a river for noodles. "Point six kilometres. I can smell it from here." |
| 3 | The Review Skeptic | the higher rating, weighted by review count (a 4.8 from 30 reviews loses to a 4.5 from 1,200) | Trusts nothing with under a hundred reviews. |
| 4 | The Craving Whisperer | more of tonight's stated cravings | Speaks only for stomachs. Quotes the cravings back. |
| 5 | The Allergy Lawyer | more of the group's needs confirmed by the restaurant | Deadly serious, the only critic who never jokes about the subject itself. |
| 6 | The Wait-Time Prophet | the shorter stated wait | Has seen the line. Counts minutes like a countdown. |
| 7 | The Adventurous One | a cuisine the group has not eaten lately | Bored of everything you had this week. |
| 8 | The Comfort Food Loyalist | a cuisine on someone's all-time favorites list | Sworn enemy of number 7. |
| 9 | The Vibe Curator | more matches to tonight's vibe tags | Cares about the lighting and the volume. |
| 10 | The Group Chat Diplomat | the place where the least happy person is happiest | Protects the quiet friend who always says "I don't mind". |

## Match rules

- Early rounds: three critics per match, rotating so all ten appear.
- The final: all ten critics vote.
- A tie (or every critic abstaining) goes to the group's overall fit score, then the
  review-weighted rating, then the higher seed. Say "tie broken by group fit" on screen.
- Byes: when the survivors are not a power of two, the top seeds skip round one.

## Writing the lines

- One line per critic, in character, naming the real number: price level, km, minutes, rating
  and review count, the craving it matches.
- Escalate across rounds: polite in round one, theatrical in the final.
- An abstaining critic gets a short line too ("Both 2. I have nothing. I abstain in disgust.").
- Never let the Allergy Lawyer's line be the punchline about the allergy itself.

## Before the bracket: elimination stages

| Stage | Cuts a place when |
|---|---|
| Allergy Tribunal | the place says it cannot accommodate a group need, or it has not confirmed a severe allergy (or any need, with `--strict`) |
| Budget Executioner | its price level is above the lowest max price in the group |
| Veto Box | anyone vetoed its cuisine or its name |
| Closed Sign | it is not open when the group wants to eat |

Survivors with a need that is not confirmed carry a CALL AHEAD flag to the end.

## Where the pattern comes from

The arena idea is public and older than any skill: candidates meet head to head, judges compare
each pair, and winners advance. It is how the Chatbot Arena leaderboard ranks language models from
pairwise votes (Zheng et al., 2023, "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena") and
how every single-elimination sports bracket works. This skill uses a standard seeded knockout with
rule-based judges, written from scratch for restaurants.
