---
name: dinner-arena
description: Ends the "where do you want to eat?" argument. Ten Claude food critics fight it out in a knockout bracket over real restaurants near you, after an Allergy Tribunal and a Budget Executioner cut anything that does not work for everyone. One restaurant survives, with a backup and a message ready for the group chat. Use when someone says "where should we eat", "pick a restaurant", "settle dinner", "we can't decide where to eat", "dinner arena", "make the Claudes fight over dinner", "restaurant bracket", "choose for the group", or "where should we go tonight".
---

# Dinner Arena

One job: turn a group that cannot decide into one restaurant, fairly, in about two minutes.

The tools actually run: `scripts/arena.py` is plain Python (standard library only). It applies the
hard rules, seeds a knockout bracket, has ten critic personas vote on every match from the real
data, and keeps the state in `./.dinner-arena/state.json`. Every vote is computed, so the result is
reproducible. You (Claude) give each critic a voice. If code execution is off, run the same rules
by hand from `references/critics.md` and say so.
Paths to `scripts/` and `references/` are inside this skill's own folder (usually
`~/.claude/skills/dinner-arena/`), not the user's current folder. Call scripts by that full path.

## Steps

1. **Group intake.** Ask once, in one message: who is eating (names or "me + 3"), each person's
   max price level (1 = cheap, 4 = splurge), dietary needs and allergies (and whether an allergy is
   severe), cravings tonight, all-time favorites, hard vetoes, what the group ate recently, the
   vibe (casual, quiet, loud, date, kid-friendly, outdoor) and the area or address. Missing
   answers are fine; do not interrogate. If the first message already answers most of it, skip
   the questions and go.
2. **Find real places.** The best source is a screenshot of a maps search ("restaurants", open
   now, near them): it shows the rating, review count, price level and distance in one go, so
   offer that first. Otherwise, with web search on, find 6 to 16 restaurants that are open at
   the time they plan to eat, in or near that area, and pull the rating, review count and price
   level from listing pages, not only articles. Record name, cuisines, price level, rating and
   review count, distance, opening hours, typical wait if stated, diet options the restaurant
   itself states, anything it says it cannot accommodate, and its website or map link. **Never
   invent a restaurant or a detail.** Unknown fields stay out of the JSON. If the tool prints
   THIN DATA, tell the user the critics had little to vote on and that a maps screenshot fixes it.
3. Write `group.json` and `places.json` in the shapes shown in `examples/`. A need that is not
   negotiable (strict halal, kosher) can be written as `{"item": "halal", "severe": true}` so it
   is enforced like a severe allergy.
4. **Allergy Tribunal + Budget Executioner.** Run
   `python scripts/arena.py new --group group.json --places places.json`
   (add `--strict` if anyone wants every need confirmed). Read out each elimination with its
   reason. Severe allergies already eliminate any place that has not confirmed it can cope.
   If that leaves nothing, say so plainly and suggest calling two or three places; when one
   confirms, add the need to its `diet` and run `new` again. Never drop or downgrade a severe
   allergy yourself to get a winner. Only the person with the allergy can decide to go on
   without a confirmation, and then every line of the result is marked provisional.
5. **The Bracket.** Show the seeded bracket. Then `python scripts/arena.py fight` one round at a
   time. For each match, give every critic who voted one line in character (see
   `references/critics.md`), naming the real number behind the vote. Do not change a vote.
6. **The Final.** All ten critics vote in the final. Make it a moment: ten lines, then the count.
7. **Crowd Override.** If the group disagrees with a result, they win:
   `python scripts/arena.py override <match> --winner "<name>" --reason "<why>"`, then fight on.
8. **Last Restaurant Standing.** `python scripts/arena.py final` prints the winner, the backup,
   any CALL AHEAD warning and a group chat message. Add the booking or map link if you found one.

## Hard rules

- Real places only, with details you found or the user gave. Say when a detail is unconfirmed.
- An allergy is never a joke. Any CALL AHEAD flag goes in the final message in plain words, and
  severe allergies are filtered by the rules, not by a critic's opinion.
- Never say a restaurant is safe for an allergy. The most it can be is "says it can cater for
  it". Whoever books tells the restaurant about the allergy, every time; the final card says so.
- Never book, order or pay for anything. Give the link; the user books.
- No mocking real restaurants' staff or reviewers by name. Roast the menu, prices and waits.
- Keep people's food needs inside this chat.

## What to hand back

The eliminations, the bracket, each round's votes with one-liners, the final count, then the
winner card and the group chat message in a copyable block. End with one question:
**"Want me to find the booking link for <winner>?"**
