from django.test import SimpleTestCase

from .matching import assign, load_balance_index


class MatchingTests(SimpleTestCase):
    def setUp(self):
        self.members = [
            {"id": 1, "skills": {"Python": 5, "SQL": 4}, "load": 0, "capacity": 35},
            {"id": 2, "skills": {"UX Research": 5, "Figma": 4}, "load": 0, "capacity": 35},
        ]

    def test_skill_drives_assignment(self):
        tasks = [
            {"ref": "T1", "title": "API", "skills": ["Python"], "hours": 8},
            {"ref": "T2", "title": "Interviews", "skills": ["UX Research"], "hours": 8},
        ]
        res = {r["ref"]: r["member_id"] for r in assign(tasks, self.members)}
        self.assertEqual(res, {"T1": 1, "T2": 2})

    def test_load_is_balanced(self):
        tasks = [{"ref": f"T{i}", "title": "x", "skills": [], "hours": 8} for i in range(6)]
        res = assign(tasks, self.members)
        counts = [sum(1 for r in res if r["member_id"] == m["id"]) for m in self.members]
        self.assertEqual(sorted(counts), [3, 3])

    def test_balance_index(self):
        self.assertAlmostEqual(load_balance_index([10, 10]), 1.0)
        self.assertLess(load_balance_index([20, 0]), 0.5)