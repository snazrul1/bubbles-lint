from bubbles_lint.rules.ai_smells import AiSmellRule
from bubbles_lint.rules.boundaries import BoundaryRule
from bubbles_lint.rules.leaks import LeakRule
from bubbles_lint.rules.size import SizeRule


def default_rules():
    return [
        SizeRule(),
        LeakRule(),
        BoundaryRule(),
        AiSmellRule(),
    ]
