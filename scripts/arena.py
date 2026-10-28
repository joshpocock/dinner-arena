#!/usr/bin/env python3
"""Dinner Arena: ten critics, one bracket, one restaurant left standing.

Standard library only. The pattern is the public "arena" idea from model evaluation:
candidates meet in head-to-head battles, judges vote on each pair, and winners advance
through a single-elimination bracket. Every vote here is computed from the data you give
it, so the result is reproducible; Claude supplies the trash talk.

Usage:
  python arena.py new --group group.json --places places.json [--strict] [--dir .dinner-arena]
  python arena.py status
  python arena.py fight            # run the next round (each match: 3 critics; final: all 10)
  python arena.py fight --all      # run to the end
  python arena.py override MATCH --winner NAME --reason "..."   # the group outvotes the critics
  python arena.py final            # Last Restaurant Standing + a message for the group chat

group.json:  {"occasion": "...", "vibe": ["casual"], "recent": ["pizza"],
              "people": [{"name": "Sam", "max_price": 2, "needs": ["vegetarian"],
                          "allergies": [{"item": "nut-free", "severe": true}],
                          "cravings": ["thai"], "favorites": ["ramen"], "vetoes": ["sushi"]}]}
places.json: [{"name": "...", "cuisine": ["thai"], "price": 2, "rating": 4.5, "reviews": 812,
               "distance_km": 1.2, "open_now": true, "wait_min": 15, "diet": ["vegetarian"],
               "unsafe_for": [], "vibe": ["casual"], "url": "https://..."}]
"""
import argparse
import json
import math
import os
import sys

CRITICS = [
    ("The Budget Executioner", "cheaper wins"),
    ("The Distance Hater", "closer wins"),
    ("The Review Skeptic", "better rating, weighted by how many reviews"),
    ("The Craving Whisperer", "matches more of tonight's cravings"),
    ("The Allergy Lawyer", "more of the group's needs the restaurant itself confirms"),
    ("The Wait-Time Prophet", "shorter wait"),
    ("The Adventurous One", "something the group has not eaten lately"),
    ("The Comfort Food Loyalist", "one of the group's favorites"),
    ("The Vibe Curator", "fits tonight's vibe"),
    ("The Group Chat Diplomat", "the least unhappy person is happiest"),
]


def as_list(xs):
    """A single string counts as one item, not a list of letters."""
    if xs is None:
        return []
    if isinstance(xs, (str, int, float)):
        return [xs]
    return list(xs)


def low(xs):
    return {str(x).strip().lower() for x in as_list(xs) if str(x).strip()}


# ---- diet and allergy words: "tree-nut free", "Tree nuts" and "tree nut allergy" are one need ----
DIETS = {"vegetarian", "vegan", "halal", "kosher", "pescatarian", "keto", "paleo"}
NUTS = {"nut", "peanut", "tree nut", "almond", "cashew", "walnut", "pecan", "pistachio",
        "hazelnut", "macadamia", "brazil nut", "pine nut"}
SAME = {"celiac": "gluten", "coeliac": "gluten", "wheat": "gluten", "milk": "dairy",
        "lactose": "dairy", "groundnut": "peanut"}


def canon(word):
    w = str(word).strip().lower().replace("_", " ").replace("-", " ")
    for suffix in (" free", " allergy", " allergies", " intolerance", " friendly", " options"):
        if w.endswith(suffix):
            w = w[: -len(suffix)]
    if w.startswith("no "):
        w = w[3:]
    w = " ".join(w.split())
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        w = w[:-1]
    return SAME.get(w, w)


def canon_set(xs):
    return {canon(x) for x in as_list(xs) if str(x).strip()}


def label(need):
    """How a need reads out loud: "vegan", "nut allergy"."""
    return need if need in DIETS else f"{need} allergy"


def covers(diet, need):
    """Does a restaurant's stated diet option confirm this need?"""
    if need in diet:
        return True
    if need == "vegetarian" and "vegan" in diet:
        return True
    return need in NUTS and "nut" in diet  # "nut-free" covers peanuts and tree nuts


def clashes(unsafe, need):
    """Does something the restaurant says it cannot handle hit this need? Errs towards yes."""
    for u in unsafe:
        if u == need or u in need or need in u:
            return True
        if u in NUTS and need in NUTS:
            return True
    return False


def person_needs(person):
    """[(need, severe, is_allergy)] from "needs" and "allergies". Either list takes plain strings
    or {"item": ..., "severe": true}; a severe need (say, strict halal) is enforced like an allergy."""
    out = []
    for key, is_allergy in (("needs", False), ("allergies", True)):
        for a in as_list(person.get(key)):
            item = a.get("item") if isinstance(a, dict) else a
            if item is None or not str(item).strip():
                continue
            sev = isinstance(a, dict) and a.get("severe") not in (None, False, "no", "false", 0)
            out.append((canon(item), sev, is_allergy))
    return out


def group_needs(group):
    needs, severe, allergies = set(), set(), set()
    for p in group.get("people", []):
        for item, sev, is_allergy in person_needs(p):
            needs.add(item)
            if sev:
                severe.add(item)
            if is_allergy:
                allergies.add(item)
    return needs, severe, allergies


def number(v):
    """Price "$$" -> 2, "15 min" -> 15, "1.2 km" -> 1.2, rubbish -> None."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v
    s = str(v).strip()
    if s and all(c in "$£€¥₹" for c in s):
        return len(s)
    num = ""
    for c in s.replace(",", ""):
        if c.isdigit() or (c == "." and "." not in num):
            num += c
        elif num:
            break
    try:
        return float(num) if "." in num else int(num)
    except ValueError:
        return None


def clean_place(pl):
    pl = dict(pl)
    for k in ("price", "rating", "reviews", "distance_km", "wait_min"):
        if k in pl:
            pl[k] = number(pl[k])
    for k in ("cuisine", "diet", "unsafe_for", "vibe"):
        pl[k] = [str(x) for x in as_list(pl.get(k))]
    o = pl.get("open_now")
    if isinstance(o, str):
        pl["open_now"] = o.strip().lower() not in ("false", "no", "closed", "0")
    return pl


def person_fit(person, place):
    """0..1: how happy one person is with one place."""
    s = 0.0
    if place.get("price") is None or place["price"] <= (number(person.get("max_price")) or 4):
        s += 0.4
    if low(person.get("cravings")) & low(place.get("cuisine")):
        s += 0.35
    if low(person.get("favorites")) & low(place.get("cuisine")):
        s += 0.15
    mine = {n for n, _, _ in person_needs(person)}
    diet = canon_set(place.get("diet"))
    if all(covers(diet, n) for n in mine):
        s += 0.1
    return round(s, 3)


def group_fit(group, place):
    fits = [person_fit(p, place) for p in group.get("people", [])] or [0.5]
    return round(sum(fits) / len(fits), 3)


def tribunal(group, places, strict=False):
    """Allergy Tribunal, Budget Executioner, Veto Box and Closed Sign. Returns (alive, dead, cap)."""
    needs, severe, _ = group_needs(group)
    cap = min([number(p.get("max_price")) or 4 for p in group.get("people", [])] or [4])
    vetoes = set()
    for p in group.get("people", []):
        vetoes |= low(p.get("vetoes"))
    alive, dead = [], []
    for i, pl in enumerate(places):
        pl = clean_place(pl)
        name, why = str(pl.get("name") or "").strip(), None
        if not name:
            dead.append({"name": f"place #{i + 1}", "stage": "Missing Name", "why": "no name, so nobody can book it"})
            continue
        pl["name"] = name
        diet, unsafe_for = canon_set(pl.get("diet")), canon_set(pl.get("unsafe_for"))
        unsafe = {n for n in needs if clashes(unsafe_for, n)}
        unconfirmed = {n for n in needs if not covers(diet, n)}
        if unsafe:
            why = ("Allergy Tribunal", f"says it can't cater for: {', '.join(label(n) for n in sorted(unsafe))}")
        elif unconfirmed & severe or (strict and unconfirmed):
            hit = unconfirmed if strict else unconfirmed & severe
            sev = "" if strict else " (severe)"
            why = ("Allergy Tribunal", f"has not confirmed it can handle: {', '.join(label(n) for n in sorted(hit))}{sev}")
        elif pl.get("price") is not None and pl["price"] > cap:
            why = ("Budget Executioner", f"price level {pl['price']} is over the group cap of {cap}")
        elif low(pl.get("cuisine")) & vetoes or name.lower() in vetoes:
            why = ("Veto Box", "someone vetoed it")
        elif pl.get("open_now") is False:
            why = ("Closed Sign", "not open tonight")
        if why:
            dead.append({"name": name, "stage": why[0], "why": why[1]})
            continue
        pl["call_ahead"] = [label(n) for n in sorted(unconfirmed)]
        pl["unknown"] = [k for k in ("price", "open_now") if pl.get(k) is None]
        pl["fit"] = group_fit(group, pl)
        alive.append(pl)
    return alive, dead, cap


def seed_order(n):
    """Standard bracket order for n (a power of two): 1 v n, then the halves mirror."""
    order = [1]
    while len(order) < n:
        m = len(order) * 2
        order = [x for s in order for x in (s, m + 1 - s)]
    return order


def build_bracket(alive):
    ranked = sorted(alive, key=lambda p: (-p["fit"], -(p.get("rating") or 0), p["name"]))
    size = 1 << max(1, math.ceil(math.log2(len(ranked))))
    slots = [ranked[s - 1]["name"] if s <= len(ranked) else None for s in seed_order(size)]
    round1 = []
    for i in range(0, size, 2):
        round1.append({"id": f"R1M{i // 2 + 1}", "a": slots[i], "b": slots[i + 1], "winner": None})
    return ranked, [round1]


# ---- critic votes: each critic compares the two places on one criterion ----
def bayes(p):
    r, n = p.get("rating"), p.get("reviews") or 0
    if r is None:
        return None
    return (r * n + 4.0 * 50) / (n + 50)


def critic_value(idx, place, group, needs):
    if idx == 0:
        return None if place.get("price") is None else -place["price"]
    if idx == 1:
        return None if place.get("distance_km") is None else -place["distance_km"]
    if idx == 2:
        return bayes(place)
    if idx == 3:
        cr = set()
        for p in group.get("people", []):
            cr |= low(p.get("cravings"))
        return len(cr & low(place.get("cuisine")))
    if idx == 4:
        diet = canon_set(place.get("diet"))
        return sum(covers(diet, n) for n in needs) - len(place.get("call_ahead", []))
    if idx == 5:
        return None if place.get("wait_min") is None else -place["wait_min"]
    if idx == 6:
        return 0 if low(group.get("recent")) & low(place.get("cuisine")) else 1
    if idx == 7:
        fav = set()
        for p in group.get("people", []):
            fav |= low(p.get("favorites"))
        return len(fav & low(place.get("cuisine")))
    if idx == 8:
        return len(low(group.get("vibe")) & low(place.get("vibe")))
    if idx == 9:
        return min(person_fit(p, place) for p in group.get("people", [])) if group.get("people") else 0
    raise ValueError(idx)


def battle(state, match, critic_ids):
    by = {p["name"]: p for p in state["alive"]}
    a, b = by[match["a"]], by[match["b"]]
    needs = set(state["needs"])
    votes = []
    for c in critic_ids:
        va, vb = critic_value(c, a, state["group"], needs), critic_value(c, b, state["group"], needs)
        if va is None or vb is None or va == vb:
            pick = None
        else:
            pick = a["name"] if va > vb else b["name"]
        votes.append({"critic": CRITICS[c][0], "rule": CRITICS[c][1], "vote": pick,
                      "a_value": va, "b_value": vb})
    ca = sum(v["vote"] == a["name"] for v in votes)
    cb = sum(v["vote"] == b["name"] for v in votes)
    if ca == cb:  # tie or all abstain: the group's overall fit decides, then rating, then seed
        key = lambda p: (p["fit"], bayes(p) or 0, -state["seed"][p["name"]])
        winner = max((a, b), key=key)["name"]
        tiebreak = "group fit"
    else:
        winner, tiebreak = (a["name"] if ca > cb else b["name"]), None
    match.update(winner=winner, votes=votes, score=f"{max(ca, cb)}-{min(ca, cb)}", tiebreak=tiebreak)


def critics_for(state, final):
    if final:
        return list(range(10))
    k = state["critic_cursor"]
    state["critic_cursor"] = k + 3
    return [(k + i) % 10 for i in range(3)]


def run_round(state):
    rnd = state["rounds"][-1]
    final = len(rnd) == 1
    for m in rnd:
        if m["winner"]:
            continue
        if m["b"] is None or m["a"] is None:
            m.update(winner=m["a"] or m["b"], votes=[], score="bye", tiebreak=None)
            continue
        battle(state, m, critics_for(state, final))
    winners = [m["winner"] for m in rnd]
    if len(winners) > 1:
        n = len(state["rounds"]) + 1
        state["rounds"].append([{"id": f"R{n}M{i // 2 + 1}", "a": winners[i], "b": winners[i + 1],
                                 "winner": None} for i in range(0, len(winners), 2)])
    else:
        state["champion"] = winners[0]
    return rnd


def round_name(state, i):
    left = len(state["rounds"][i])
    return {1: "THE FINAL", 2: "SEMI-FINALS", 4: "QUARTER-FINALS"}.get(left, f"ROUND {i + 1}")


def print_match(m):
    if m.get("score") == "bye" or m["a"] is None or m["b"] is None:
        print(f"  {m['id']}: {m['a'] or m['b']} gets a bye")
        return
    print(f"  {m['id']}: {m['a']}  vs  {m['b']}")
    for v in m.get("votes", []):
        print(f"      {v['critic']:<26} -> {v['vote'] or 'abstains (tie)'}   [{v['rule']}]")
    if m.get("winner"):
        tb = f" (tie broken by {m['tiebreak']})" if m.get("tiebreak") else ""
        how = m.get("override") or f"{m['score']}{tb}"
        print(f"      SURVIVES: {m['winner']}  {how}")


def load(d):
    p = os.path.join(d, "state.json")
    if not os.path.exists(p):
        sys.exit("No arena yet. Start one with: arena.py new --group group.json --places places.json")
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def save(d, state):
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "state.json"), "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, ensure_ascii=False)


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Dinner Arena bracket engine")
    ap.add_argument("--dir", default=".dinner-arena")
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new")
    n.add_argument("--group", required=True)
    n.add_argument("--places", required=True)
    n.add_argument("--strict", action="store_true", help="also eliminate places that cannot confirm every need")
    sub.add_parser("status")
    f = sub.add_parser("fight")
    f.add_argument("--all", action="store_true")
    o = sub.add_parser("override")
    o.add_argument("match")
    o.add_argument("--winner", required=True)
    o.add_argument("--reason", required=True)
    sub.add_parser("final")
    a = ap.parse_args(argv)

    if a.cmd == "new":
        group, places = read_json(a.group), read_json(a.places)
        if len(places) > 16:
            sys.exit("Sixteen places maximum. Cut the list first.")
        needs, _, allergies = group_needs(group)
        alive, dead, cap = tribunal(group, places, a.strict)
        print(f"ALLERGY TRIBUNAL + BUDGET EXECUTIONER  (group needs: {', '.join(label(n) for n in sorted(needs)) or 'none'}; price cap {cap})")
        for d in dead:
            print(f"  ELIMINATED  {d['name']:<28} {d['stage']}: {d['why']}")
        if not alive:
            if any(d["stage"] == "Allergy Tribunal" and "has not confirmed" in d["why"] for d in dead):
                sys.exit("Nothing survived the tribunal. No place has confirmed it can handle a severe need.\n"
                         "Call two or three of them and ask. Add the need to the diet list of any place that\n"
                         "says yes, then run `new` again. Do not drop it to get a winner.")
            sys.exit("Nothing survived the tribunal. Add places, or loosen a budget or a veto (never an allergy).")
        if len(alive) < 2:
            sys.exit(f"Only {alive[0]['name']} survived the tribunal. No bracket needed; that's your answer.")
        ranked, rounds = build_bracket(alive)
        state = {"group": group, "needs": sorted(needs), "allergies": sorted(allergies),
                 "alive": alive, "dead": dead,
                 "seed": {p["name"]: i + 1 for i, p in enumerate(ranked)},
                 "rounds": rounds, "critic_cursor": 0, "champion": None}
        save(a.dir, state)
        thin = [k for k in ("price", "rating", "distance_km")
                if sum(p.get(k) is None for p in alive) * 2 > len(alive)]
        if thin:
            print(f"\nTHIN DATA: most survivors have no {', '.join(t.replace('_km', '') for t in thin)}. Critics abstain"
                  " on missing numbers, so ties fall to group fit and then seed. Add the numbers from a maps"
                  " listing for a real fight.")
        print(f"\nTHE BRACKET  ({len(alive)} survivors, seeded by group fit)")
        for p in ranked:
            flag = f"  CALL AHEAD: {', '.join(p['call_ahead'])}" if p["call_ahead"] else ""
            if "price" in p["unknown"]:
                flag += "  PRICE UNKNOWN"
            print(f"  #{state['seed'][p['name']]:<2} {p['name']:<28} fit {p['fit']:.2f}{flag}")
        print()
        for m in rounds[0]:
            print_match(m)
        return 0

    state = load(a.dir)
    if a.cmd == "status":
        for i, rnd in enumerate(state["rounds"]):
            print(round_name(state, i))
            for m in rnd:
                print_match(m)
        if state["champion"]:
            print(f"\nLAST RESTAURANT STANDING: {state['champion']}")
        return 0
    if a.cmd == "fight":
        while not state["champion"]:
            i = len(state["rounds"]) - 1
            print(round_name(state, i))
            for m in run_round(state):
                print_match(m)
            print()
            if not a.all:
                break
        save(a.dir, state)
        if state["champion"]:
            print(f"LAST RESTAURANT STANDING: {state['champion']}  (run `final` for the group chat message)")
        return 0
    if a.cmd == "override":
        for i, rnd in enumerate(state["rounds"]):
            for m in rnd:
                if m["id"] == a.match:
                    if a.winner not in (m["a"], m["b"]):
                        sys.exit(f"{a.winner} is not in {a.match}")
                    m["winner"], m["override"] = a.winner, f"CROWD OVERRIDE: {a.reason}"
                    state["rounds"] = state["rounds"][: i + 1]
                    state["champion"] = None
                    winners = [x["winner"] for x in rnd]
                    if all(winners) and len(winners) > 1:
                        state["rounds"].append([{"id": f"R{i + 2}M{k // 2 + 1}", "a": winners[k],
                                                 "b": winners[k + 1], "winner": None}
                                                for k in range(0, len(winners), 2)])
                    elif all(winners):
                        state["champion"] = winners[0]
                    save(a.dir, state)
                    print(f"{a.match}: {a.winner} advances by crowd override. Later rounds reset.")
                    return 0
        sys.exit(f"No match {a.match}")
    if a.cmd == "final":
        if not state["champion"]:
            sys.exit("No champion yet. Run: arena.py fight --all")
        by = {p["name"]: p for p in state["alive"]}
        champ = by[state["champion"]]
        final = state["rounds"][-1][0]
        runner = final["b"] if final["winner"] == final["a"] else final["a"]
        backup = by[runner]
        print(f"LAST RESTAURANT STANDING: {champ['name']}")
        print(f"  {', '.join(champ.get('cuisine', []))} | price {champ.get('price') or '?'} | "
              f"{champ.get('distance_km') or '?'} km | rating {champ.get('rating') or '?'}")
        if champ.get("url"):
            print(f"  {champ['url']}")
        if champ.get("call_ahead"):
            print(f"  CALL AHEAD to confirm: {', '.join(champ['call_ahead'])}")
        allergies = state.get("allergies", [])
        if allergies:
            print(f"  ALLERGY: tell them about the {', '.join(label(x) for x in allergies)} when you book, even if the"
                  " menu says it's fine. A website label is not a guarantee.")
        if "price" in champ.get("unknown", []):
            print("  PRICE UNKNOWN: check the menu before you go.")
        bflag = f" (call ahead: {', '.join(backup['call_ahead'])})" if backup.get("call_ahead") else ""
        print(f"  Backup if it's full: {runner}{bflag}")
        print(f"  Final vote: {final.get('override') or final.get('score')}")
        print("\nGROUP CHAT MESSAGE:")
        url = f" {champ['url']}" if champ.get("url") else ""
        if champ.get("call_ahead"):
            ca = f" Calling ahead first about the {', '.join(champ['call_ahead'])}."
        elif allergies:
            ca = f" I'll still tell them about the {', '.join(label(x) for x in allergies)} when I book."
        else:
            ca = ""
        print(f"  Ten critics fought. {champ['name']} survived.{url}{ca} Backup is {runner}."
              " Booking unless someone objects in 10 min.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
