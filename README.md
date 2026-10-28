# Dinner Arena

One Claude skill that ends "where do you want to eat?" Ten Claude food critics fight it out in a
knockout bracket over real restaurants near you, and one survives. Free, MIT, no signup, no API
key, nothing to connect.

**It never books, orders or pays for anything. Allergies are handled by hard rules, not by a
critic's opinion, and it never calls a restaurant allergy-safe: whoever books tells them.**

## Install

**Claude Code, one paste.** Paste this into Claude Code:

```
Install the Dinner Arena skill: clone https://github.com/joshpocock/dinner-arena into ~/.claude/skills/dinner-arena, then confirm /dinner-arena works.
```

Or in a terminal:

```
git clone https://github.com/joshpocock/dinner-arena ~/.claude/skills/dinner-arena
```

Start a new Claude Code session and type `/dinner-arena`, then say who's eating, where, and
anything they can't eat. Keep web search on so Claude can find real places, or paste a
screenshot of a maps search: that gives the critics the best numbers.

**Claude.ai (website or app).** Turn on Settings, Capabilities, **Code execution and file
creation**, and keep web search on. On this GitHub page click Code, Download ZIP. In Claude go to
Customize, Skills, +, Upload a skill, and pick the zip. Start a new chat and say "use the
dinner-arena skill".

**Any chat, no install.** Paste `SKILL.md` and `references/critics.md` into a chat; Claude runs
the bracket by hand.

## How it works

| Stage | What happens |
|---|---|
| Group intake | Who is eating, budgets, diets and allergies, cravings, favorites, vetoes, the vibe |
| Real places | A maps screenshot you paste, or 6 to 16 open restaurants Claude finds with web search. Nothing invented |
| Allergy Tribunal | Out if the place says it can't cater for a need, or has not confirmed a severe allergy |
| Budget Executioner | Out if it is above the cheapest person's limit |
| Veto Box, Closed Sign | Out if anyone vetoed it or it is closed |
| The Bracket | Survivors seeded by how well they fit the whole group |
| The Battles | Three critics vote on each match, each on one rule; all ten vote in the final |
| Crowd Override | The humans can overrule any result |
| Last Restaurant Standing | Winner, backup, call-ahead and allergy warnings, and a message for the group chat |

The ten critics: the Budget Executioner, the Distance Hater, the Review Skeptic, the Craving
Whisperer, the Allergy Lawyer, the Wait-Time Prophet, the Adventurous One, the Comfort Food
Loyalist, the Vibe Curator and the Group Chat Diplomat. Each votes on one real number, so the same
inputs always give the same winner. Claude writes their trash talk.

## One dinner, start to finish

A made-up example, real tool output (the data is in `examples/`). Four friends, one vegetarian,
one nut allergy, the cheapest budget at price level 2, eleven places.

```
ALLERGY TRIBUNAL + BUDGET EXECUTIONER  (group needs: nut allergy, vegetarian; price cap 2)
  ELIMINATED  EXAMPLE Ember Steakhouse     Budget Executioner: price level 4 is over the group cap of 2
  ELIMINATED  EXAMPLE Sushi Wave           Budget Executioner: price level 3 is over the group cap of 2
  ELIMINATED  EXAMPLE Satay House          Allergy Tribunal: says it can't cater for: nut allergy
  ELIMINATED  EXAMPLE Nonna's Pizza        Closed Sign: not open tonight
...
THE FINAL
  R3M1: EXAMPLE Lotus Thai Kitchen  vs  EXAMPLE Masala Street
      The Distance Hater         -> EXAMPLE Lotus Thai Kitchen   [closer wins]
      The Review Skeptic         -> EXAMPLE Masala Street   [better rating, weighted by how many reviews]
      ...
      SURVIVES: EXAMPLE Lotus Thai Kitchen  3-3 (tie broken by group fit)

LAST RESTAURANT STANDING: EXAMPLE Lotus Thai Kitchen
  thai, noodles | price 2 | 1.2 km | rating 4.5
  CALL AHEAD to confirm: nut allergy
  ALLERGY: tell them about the nut allergy when you book, even if the menu says it's fine. A website label is not a guarantee.
  Backup if it's full: EXAMPLE Masala Street
  Final vote: 3-3

GROUP CHAT MESSAGE:
  Ten critics fought. EXAMPLE Lotus Thai Kitchen survived. Calling ahead first about the nut allergy. Backup is EXAMPLE Masala Street. Booking unless someone objects in 10 min.
```

If nobody has confirmed a severe allergy, nothing survives, and the tool tells you to call two or
three places instead of quietly dropping the allergy.

## The tool

`scripts/arena.py` is plain Python 3 with no installs.

```
python scripts/arena.py new --group examples/group.json --places examples/places.json
python scripts/arena.py fight            # one round
python scripts/arena.py fight --all      # to the end
python scripts/arena.py override R3M1 --winner "EXAMPLE Masala Street" --reason "Alex had Thai for lunch"
python scripts/arena.py final
python -m unittest discover -s tests     # 13 tests
```

State lives in `.dinner-arena/state.json` in the folder you run it from. Prices can be numbers
or "$$"; "tree-nut free", "Tree nuts" and "tree nut allergy" count as the same need.

## Where the idea comes from

Head-to-head battles judged in pairs, winners advancing: the same public pattern behind the
Chatbot Arena model leaderboard and every knockout sports bracket. This version is written from
scratch for restaurants. The restaurants in `examples/` are made up.

## Fine print

- Ratings, prices and hours come from what Claude finds or what you give it. Check before you go.
- If someone has a serious allergy, call the restaurant. A website saying "vegetarian options" or
  even "nut-free" is not an allergy guarantee.

## More free skills

- [Don't Text Them](https://github.com/joshpocock/dont-text-them) (stops the 2am text)
- [Parent Tech Support](https://github.com/joshpocock/parent-tech-support) (patient tech help and scam checks for your parents)

Made by Josh Pocock. More at [strideaiacademy.com](https://strideaiacademy.com).

MIT licence.
