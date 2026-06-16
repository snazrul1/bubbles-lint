from bubbles.rules.ai_smells import AiSmellRule
from bubbles.rules.boundaries import BoundaryRule
from bubbles.rules.leaks import LeakRule
from bubbles.rules.size import SizeRule


def default_rules():
    return [
        SizeRule(),
        LeakRule(),
        BoundaryRule(),
        AiSmellRule(),
    ]
