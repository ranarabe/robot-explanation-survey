"""All rules, grouped by source. Swap ALGORITHM_RULES if the algorithm changes."""

from .algorithm import ALGORITHM
from .algorithm import RULES as ALGORITHM_RULES
from .base import Rule, conclude, rule
from .environment import RULES as ENVIRONMENT_RULES
from .physics import RULES as PHYSICS_RULES

DEFAULT_RULES = ENVIRONMENT_RULES + PHYSICS_RULES + ALGORITHM_RULES

__all__ = [
    'Rule', 'rule', 'conclude', 'ALGORITHM',
    'ENVIRONMENT_RULES', 'PHYSICS_RULES', 'ALGORITHM_RULES', 'DEFAULT_RULES',
]
