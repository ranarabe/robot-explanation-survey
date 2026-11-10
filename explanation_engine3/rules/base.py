"""How a rule is written.

A rule is a normal Python function decorated with @rule(...).
The function receives the knowledge base and YIELDS new facts
using conclude(...). The engine sets the rule name and source.

Example:

    @rule('under', source='physics',
          if_text='Y on_top_of Z',
          then_text='Z under Y')
    def under(kb):
        for fact in kb.facts(predicate='on_top_of'):
            yield conclude(fact.object, 'under', fact.subject, premises=[fact])
"""

from dataclasses import dataclass
from typing import Callable, Iterable

from ..facts import Fact


@dataclass
class Rule:
    name: str
    source: str
    if_text: str
    then_text: str
    function: Callable

    def apply(self, kb) -> Iterable[Fact]:
        for fact in self.function(kb):
            fact.rule = self.name
            fact.source = self.source
            yield fact

    def __str__(self) -> str:
        return f'[{self.source}] {self.name}: IF {self.if_text} THEN {self.then_text}'


def rule(name: str, source: str, if_text: str, then_text: str):
    """Decorator that turns a function into a Rule."""
    def wrap(function):
        return Rule(name, source, if_text, then_text, function)
    return wrap


def conclude(subject, predicate, object_, premises=(), layer=None, evidence=None) -> Fact:
    """Build an inferred fact. `premises` are the Fact objects that were used."""
    return Fact(
        subject=subject,
        predicate=predicate,
        object=object_,
        layer=layer,
        premises=[premise.fact_id for premise in premises],
        evidence=evidence or {},
    )
