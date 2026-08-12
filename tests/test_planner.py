import unittest
from src.core.planner import Planner, Scheduler, WorkUnit

class TestPlannerScheduler(unittest.TestCase):
    def test_planning(self):
        units = Planner.plan_task("Test prompt", ["file.pdf"])
        ids = [u.id for u in units]
        self.assertIn("unit_inspect", ids)
        # New rule-based planner generates PDF plan for .pdf files
        self.assertIn("unit_analysis", ids)
        self.assertIn("unit_aggregate", ids)

    def test_scheduling_priorities(self):
        units = [
            WorkUnit(id="p4", type="polish", priority="P4"),
            WorkUnit(id="p0", type="core", priority="P0"),
            WorkUnit(id="p2", type="val", priority="P2")
        ]
        # All eligible, should be sorted P0, P2, P4
        eligible = Scheduler.get_eligible_units(units, [], "AUTO", "NORMAL")
        self.assertEqual(eligible[0].id, "p0")
        self.assertEqual(eligible[1].id, "p2")
        self.assertEqual(eligible[2].id, "p4")

    def test_scheduling_budget_drop(self):
        units = [
            WorkUnit(id="p0", type="core", priority="P0"),
            WorkUnit(id="p4", type="polish", priority="P4", optional=True)
        ]
        # In CRITICAL state, P4 should be skipped
        eligible = Scheduler.get_eligible_units(units, [], "AUTO", "CRITICAL")
        self.assertEqual(len(eligible), 1)
        self.assertEqual(eligible[0].id, "p0")
        self.assertEqual(units[1].status, "skipped")

if __name__ == "__main__":
    unittest.main()
