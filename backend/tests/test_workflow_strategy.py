import unittest

from src.application.orchestrators.run_orchestrator import RunOrchestrator
from src.application.workflows.strategy import ActivityWorkflowStrategy, NonActivityWorkflowStrategy


class WorkflowStrategyTests(unittest.TestCase):
    def test_activity_strategy_supports_activity_only(self):
        strategy = ActivityWorkflowStrategy()
        self.assertTrue(strategy.supports("activity"))
        self.assertFalse(strategy.supports("sequence"))

    def test_non_activity_strategy_supports_non_activity(self):
        strategy = NonActivityWorkflowStrategy()
        self.assertTrue(strategy.supports("sequence"))
        self.assertFalse(strategy.supports("activity"))

    def test_orchestrator_selects_expected_strategy(self):
        orchestrator = object.__new__(RunOrchestrator)
        orchestrator.workflow_strategies = [ActivityWorkflowStrategy(), NonActivityWorkflowStrategy()]
        self.assertIsInstance(orchestrator._select_strategy("activity"), ActivityWorkflowStrategy)
        self.assertIsInstance(orchestrator._select_strategy("sequence"), NonActivityWorkflowStrategy)


if __name__ == "__main__":
    unittest.main()
