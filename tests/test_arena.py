import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import arena  # noqa: E402

EX = os.path.join(HERE, "..", "examples")


def load(name):
    with open(os.path.join(EX, name), encoding="utf-8") as fh:
        return json.load(fh)


class ArenaTests(unittest.TestCase):
    def test_tribunal_rules(self):
        alive, dead, cap = arena.tribunal(load("group.json"), load("places.json"))
        why = {d["name"]: d["stage"] for d in dead}
        self.assertEqual(cap, 2)
        self.assertEqual(why["EXAMPLE Satay House"], "Allergy Tribunal")
        self.assertEqual(why["EXAMPLE Ember Steakhouse"], "Budget Executioner")
        self.assertEqual(why["EXAMPLE Nonna's Pizza"], "Closed Sign")
        self.assertIn("EXAMPLE Sushi Wave", why)  # over budget before the veto even matters
        self.assertEqual(len(alive), 7)

    def test_severe_allergy_eliminates_unconfirmed(self):
        g = load("group.json")
        g["people"][2]["allergies"] = [{"item": "nut-free", "severe": True}]
        alive, dead, _ = arena.tribunal(g, load("places.json"))
        names = {p["name"] for p in alive}
        self.assertNotIn("EXAMPLE Lotus Thai Kitchen", names)
        self.assertIn("EXAMPLE Masala Street", names)

    def test_seed_order(self):
        self.assertEqual(arena.seed_order(8), [1, 8, 4, 5, 2, 7, 3, 6])

    def test_full_run_is_reproducible_and_every_critic_votes(self):
        champs, critics = [], set()
        for _ in range(2):
            with tempfile.TemporaryDirectory() as d:
                arena.main(["--dir", d, "new", "--group", os.path.join(EX, "group.json"),
                            "--places", os.path.join(EX, "places.json")])
                arena.main(["--dir", d, "fight", "--all"])
                st = arena.load(d)
                champs.append(st["champion"])
                for rnd in st["rounds"]:
                    for m in rnd:
                        critics |= {v["critic"] for v in m.get("votes", [])}
        self.assertEqual(champs[0], champs[1])
        self.assertEqual(len(critics), 10)

    def test_override_resets_later_rounds(self):
        with tempfile.TemporaryDirectory() as d:
            arena.main(["--dir", d, "new", "--group", os.path.join(EX, "group.json"),
                        "--places", os.path.join(EX, "places.json")])
            arena.main(["--dir", d, "fight", "--all"])
            arena.main(["--dir", d, "override", "R3M1", "--winner", "EXAMPLE Masala Street",
                        "--reason", "Sam had Thai yesterday"])
            self.assertEqual(arena.load(d)["champion"], "EXAMPLE Masala Street")


def run(argv):
    """Run the CLI, return (exit message or code, printed text)."""
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            code = arena.main(argv)
        except SystemExit as e:
            code = e.code
    return code, buf.getvalue()


def arena_from(group, places, d):
    for name, data in (("g.json", group), ("p.json", places)):
        with open(os.path.join(d, name), "w", encoding="utf-8") as fh:
            json.dump(data, fh)
    st = os.path.join(d, "st")
    return st, run(["--dir", st, "new", "--group", os.path.join(d, "g.json"),
                    "--places", os.path.join(d, "p.json")])


class RealWorldInputTests(unittest.TestCase):
    """Bugs found on realistic inputs outside the demo, 2026-10-28. One test per fix."""

    def test_unsafe_spelled_differently_still_eliminates(self):
        # Before: "unsafe_for": ["peanuts"] did not match a "nut-free" need, and the place
        # survived as the backup. Now any nut word clashes with any nut allergy.
        g = {"people": [{"name": "Priya", "allergies": [{"item": "nut-free", "severe": False}]}]}
        places = [{"name": "Satay", "price": 2, "unsafe_for": ["peanuts"]},
                  {"name": "Cafe", "price": 2, "diet": ["nut-free"]},
                  {"name": "Diner", "price": 2}]
        alive, dead, _ = arena.tribunal(g, places)
        self.assertEqual([d["name"] for d in dead], ["Satay"])
        self.assertEqual(dead[0]["stage"], "Allergy Tribunal")

    def test_spelling_variants_confirm_a_need(self):
        # Before: "tree-nut free" on the menu did not confirm a "tree nuts" allergy.
        g = {"people": [{"name": "Ben", "allergies": [{"item": "tree nuts", "severe": True}]}]}
        alive, dead, _ = arena.tribunal(g, [{"name": "Tacos", "diet": ["Tree-nut free"]},
                                            {"name": "Pho", "diet": ["vegan"]}])
        self.assertEqual([p["name"] for p in alive], ["Tacos"])
        self.assertEqual(alive[0]["call_ahead"], [])

    def test_dollar_prices_do_not_crash_and_still_count(self):
        # Before: "price": "$$$" raised TypeError in the Budget Executioner.
        g = {"people": [{"name": "Me", "max_price": "$"}]}
        alive, dead, cap = arena.tribunal(g, [{"name": "Ramen", "price": "$$$"},
                                              {"name": "Tacos", "price": "$"}])
        self.assertEqual(cap, 1)
        self.assertEqual(dead[0]["stage"], "Budget Executioner")
        self.assertEqual(alive[0]["price"], 1)

    def test_single_string_is_one_item_not_letters(self):
        # Before: "vetoes": "sushi" became {s, u, h, i}, and every restaurant was vetoed.
        g = {"people": [{"name": "A", "cravings": "thai", "vetoes": "sushi"}]}
        alive, dead, _ = arena.tribunal(g, [{"name": "Thai One", "cuisine": "thai"},
                                            {"name": "Sushi Go", "cuisine": "sushi"},
                                            {"name": "Burgers", "cuisine": "burgers"}])
        self.assertEqual([d["name"] for d in dead], ["Sushi Go"])
        self.assertGreater(alive[0]["fit"], alive[1]["fit"])

    def test_winner_always_carries_the_allergy_warning(self):
        # Before: a winner whose menu said nut-free got no allergy line at all, and the backup's
        # CALL AHEAD flag was dropped from the final card.
        g = {"people": [{"name": "Priya", "allergies": ["nuts"]}, {"name": "Theo"}]}
        places = [{"name": "Cafe", "price": 1, "rating": 4.8, "reviews": 900, "distance_km": 0.5,
                   "diet": ["nut-free"]},
                  {"name": "Diner", "price": 2, "rating": 3.9, "reviews": 90, "distance_km": 3}]
        with tempfile.TemporaryDirectory() as d:
            st, _ = arena_from(g, places, d)
            run(["--dir", st, "fight", "--all"])
            _, out = run(["--dir", st, "final"])
        self.assertIn("LAST RESTAURANT STANDING: Cafe", out)
        self.assertIn("ALLERGY: tell them about the nut allergy", out)
        self.assertIn("not a guarantee", out)
        self.assertIn("Backup if it's full: Diner (call ahead: nut allergy)", out)

    def test_severe_wipeout_says_call_and_never_drops_the_allergy(self):
        # Before: "Only nothing survived the tribunal ... loosen a rule", which invited dropping it.
        g = {"people": [{"name": "Dan", "allergies": [{"item": "peanut", "severe": True}]}]}
        with tempfile.TemporaryDirectory() as d:
            _, (code, out) = arena_from(g, [{"name": "A"}, {"name": "B"}], d)
        self.assertIn("Call two or three of them", str(code))
        self.assertIn("Do not drop it", str(code))

    def test_missing_numbers_are_flagged(self):
        # Before: unknown prices passed the budget silently and thin data gave a silent coin flip.
        g = {"people": [{"name": "Me", "max_price": 1}]}
        with tempfile.TemporaryDirectory() as d:
            _, (_, out) = arena_from(g, [{"name": "A"}, {"name": "B"}, {"name": "C", "price": 1}], d)
        self.assertIn("THIN DATA", out)
        self.assertIn("PRICE UNKNOWN", out)

    def test_severe_need_is_enforced_like_an_allergy(self):
        g = {"people": [{"name": "Z", "needs": [{"item": "halal", "severe": True}]}, {"name": "Y"}]}
        alive, dead, _ = arena.tribunal(g, [{"name": "Grill", "diet": ["Halal"]}, {"name": "Pub"}])
        self.assertEqual([p["name"] for p in alive], ["Grill"])


if __name__ == "__main__":
    unittest.main()
