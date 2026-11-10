"""Knowledge base: object info, facts and rules.

Facts live in three layers:

    static    knowledge/*.json        same for every run   (never saved in a run)
    given     added by the planner     what happened in this run
    inferred  produced by the rules    ALWAYS recomputed, never trusted from disk

Because inferred facts are recomputed from scratch, changing a rule file
and reloading an old run gives answers that follow the NEW rules.

Typical use (inside the planner):
    kb = KnowledgeBase()
    kb.add_object(Element(...))
    kb.add_fact('cube_red_37', 'has_score', 0.82, source='execution', layer=1)
    kb.add_fact('cube_red_37', 'selected_in', 'layer_1', source='execution', layer=1)
    kb.save()                       # -> src/explanation_engine3/runs/run_<time>.json

Later (answering questions):
    kb = KnowledgeBase.load(latest_run())
"""

import json
import os
import warnings
from datetime import datetime
from pathlib import Path

from .facts import SOURCES, Fact
from .objects import Element
from .rules import ALGORITHM, DEFAULT_RULES


STATIC_DIR = Path(__file__).parent / 'knowledge'
def _default_runs_dir() -> Path:
    """Where run files are saved:
    1. $EXPLANATION_RUNS_DIR if set
    2. src/explanation_engine3/runs/ inside the project (works with colcon --symlink-install)
    3. ~/.ros/explanation_engine3/runs/ otherwise
    """
    if os.environ.get('EXPLANATION_RUNS_DIR'):
        return Path(os.environ['EXPLANATION_RUNS_DIR']).expanduser()
    package_dir = Path(__file__).resolve().parent.parent      # src/explanation_engine3
    if (package_dir / 'package.xml').exists():
        return package_dir / 'runs'
    return Path('~/.ros/explanation_engine3/runs').expanduser()


RUNS_DIR = _default_runs_dir()


def latest_run() -> Path:
    """Path of the most recently saved run file."""
    runs = sorted(RUNS_DIR.glob('run_*.json'))
    if not runs:
        raise FileNotFoundError(f'No run files in {RUNS_DIR}')
    return runs[-1]


class KnowledgeBase:

    def __init__(self, rules=None, static_dir=STATIC_DIR, auto_infer=True):
        self.objects: dict[str, Element] = {}
        self.rules = list(DEFAULT_RULES if rules is None else rules)
        self.auto_infer = auto_infer
        self.path: Path | None = None       # file this KB was loaded from / saved to
        self.meta = {
            'created_at': datetime.now().isoformat(timespec='seconds'),
            'algorithm': dict(ALGORITHM),
        }
        self._static: dict[str, Fact] = {}
        self._given: dict[str, Fact] = {}
        self._inferred: dict[str, Fact] = {}
        if static_dir is not None:
            self._load_static(Path(static_dir))
        self.infer()

    # ------------------------------------------------------------------ objects

    def add_object(self, element: Element) -> None:
        if element.element_id in self.objects:
            raise ValueError(f'Object id {element.element_id!r} is already used; ids must be unique')
        self.objects[element.element_id] = element
        self._changed()

    def find_objects(self, color=None, shape=None) -> list[Element]:
        """E.g. find_objects(color='red') -> the red cube(s)."""
        return [
            element for element in self.objects.values()
            if (color is None or element.color == color)
            and (shape is None or element.shape == shape)
        ]

    # -------------------------------------------------------------------- facts

    def add_fact(self, subject, predicate, object_, source, layer=None) -> Fact:
        """Add a given fact. A value fact replaces the previous value."""
        fact = Fact(subject, predicate, object_, source=source, layer=layer)
        _check_source(fact)
        self._given[fact.fact_id] = fact
        self._changed()
        return fact

    def facts(self, subject=None, predicate=None, object_=None,
              source=None, layer=None, inferred=None) -> list[Fact]:
        """Return the facts matching every filter that is not None."""
        return [
            fact for fact in self._all_facts()
            if (subject is None or fact.subject == subject)
            and (predicate is None or fact.predicate == predicate)
            and (object_ is None or fact.object == object_)
            and (source is None or fact.source == source)
            and (layer is None or fact.layer == layer)
            and (inferred is None or fact.is_inferred == inferred)
        ]

    def get(self, fact_id: str) -> Fact | None:
        return self._given.get(fact_id) or self._inferred.get(fact_id) or self._static.get(fact_id)

    def has(self, subject, predicate, object_, layer=None) -> bool:
        return bool(self.facts(subject, predicate, object_, layer=layer))

    def value(self, subject, predicate, layer=None):
        """Number of a value fact, e.g. value('cube_red_37', 'has_score', layer=1)."""
        found = [fact for fact in self.facts(subject, predicate, layer=layer) if fact.is_value]
        return found[0].object if found else None

    def layers(self) -> list[int]:
        return sorted({fact.layer for fact in self._all_facts() if fact.layer is not None})

    def is_static(self, fact: Fact) -> bool:
        return fact.fact_id in self._static

    def _all_facts(self):
        yield from self._static.values()
        yield from self._given.values()
        yield from self._inferred.values()

    def _changed(self):
        if self.auto_infer:
            self.infer()

    # ---------------------------------------------------------------- reasoning

    def infer(self) -> list[Fact]:
        """Recompute ALL inferred facts from static + given facts.

        Forward chaining: apply every rule, repeat until nothing new appears.
        """
        self._inferred = {}
        changed = True
        while changed:
            changed = False
            for rule in self.rules:
                for fact in list(rule.apply(self)):
                    if self.get(fact.fact_id) is None:
                        self._inferred[fact.fact_id] = fact
                        changed = True
        return list(self._inferred.values())

    def support(self, fact_id: str) -> list[Fact]:
        """The fact plus every fact it depends on (premises, recursively)."""
        found, stack = {}, [fact_id]
        while stack:
            fact = self.get(stack.pop())
            if fact is None or fact.fact_id in found:
                continue
            found[fact.fact_id] = fact
            stack.extend(fact.premises)
        return list(found.values())

    def trace(self, fact_id: str, depth: int = 0) -> list[str]:
        """Explain a fact by following its premises back to given/static facts."""
        fact = self.get(fact_id)
        indent = '    ' * depth
        if fact is None:
            return [f'{indent}? {fact_id} (unknown fact)']
        if not fact.is_inferred:
            origin = 'static' if self.is_static(fact) else 'given'
            return [f'{indent}- {fact}   [{origin}, {fact.source}]']
        lines = [f'{indent}- {fact}   [rule {fact.rule}, {fact.source}]']
        for key, value in fact.evidence.items():
            lines.append(f'{indent}      because {key} = {value}')
        for premise in fact.premises:
            lines.extend(self.trace(premise, depth + 1))
        return lines

    # --------------------------------------------------------------------- json

    def to_dict(self) -> dict:
        inferred = {source: [] for source in SOURCES}
        for fact in self._inferred.values():
            inferred[fact.source].append(fact.to_dict())

        by_layer, by_object = {}, {}
        for fact in list(self._given.values()) + list(self._inferred.values()):
            if fact.layer is not None:
                by_layer.setdefault(f'layer_{fact.layer}', []).append(str(fact))
            for name in (fact.subject, fact.object):
                if name in self.objects:
                    by_object.setdefault(name, []).append(str(fact))

        return {
            'meta': self.meta,
            'objects': {key: element.to_dict() for key, element in self.objects.items()},
            # The only facts that are read back on load:
            'given': [fact.to_dict() for fact in self._given.values()],
            # Everything below is for reading only. It is rebuilt on every save
            # and ignored on load (the rules recompute it).
            'inferred': inferred,
            'index': {'by_layer': by_layer, 'by_object': by_object},
            'rules': [str(rule) for rule in self.rules],
        }

    def save(self, path=None) -> Path:
        if path is None:
            stamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            path = RUNS_DIR / f'run_{stamp}.json'
        path = Path(path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False))
        self.path = path
        return path

    @classmethod
    def load(cls, path, rules=None, static_dir=STATIC_DIR) -> 'KnowledgeBase':
        data = json.loads(Path(path).expanduser().read_text())
        kb = cls(rules=rules, static_dir=static_dir, auto_infer=False)
        kb.meta = data.get('meta', kb.meta)
        kb.path = Path(path).expanduser()
        recorded = kb.meta.get('algorithm', {})
        if (recorded.get('name'), recorded.get('version')) != (ALGORITHM['name'], ALGORITHM['version']):
            warnings.warn(
                f'Run was recorded with algorithm {kb.meta.get("algorithm")}, '
                f'current rules are {ALGORITHM}. Explanations follow the current rules.'
            )
        for element in data['objects'].values():
            kb.add_object(Element.from_dict(element))
        for fact_data in data['given']:
            fact = Fact.from_dict(fact_data)
            kb._given[fact.fact_id] = fact
        kb.infer()
        kb.auto_infer = True
        return kb

    def _load_static(self, directory: Path) -> None:
        """Read knowledge/<source>.json files, e.g. environment.json, physics.json."""
        for source in SOURCES:
            path = directory / f'{source}.json'
            if not path.exists():
                continue
            for item in json.loads(path.read_text())['facts']:
                fact = Fact(source=source, **item)
                self._static[fact.fact_id] = fact


def _check_source(fact: Fact) -> None:
    if fact.source not in SOURCES:
        raise ValueError(f'Unknown source {fact.source!r}; use one of {SOURCES}')
