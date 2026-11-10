"""Collect ONLY the facts that answer the question (no LLM here).

    why       "Why was X placed in layer n?"
              X selected_in layer n
              X preferred_over every other candidate of layer n (with stability values)
              X bigger_than / smaller than those candidates
    why_not   "Why X instead of Y in layer n?"
              the same, but only against Y, plus where Y really ended up
    what_if   "What if Y instead of X in layer n?"
              the why_not facts (why the robot chose X), plus the simulated
              alternative tower: its order, its stability, objects on smaller ones
    other     any other question: where the mentioned objects / layer are,
              and their size relation
    always    the tower order and the tower stability

Not sent: support chains, bookkeeping facts (candidate_in, best_candidate_in,
is placed), mirror facts (smaller_than, under), facts about other objects.

The what_if tower is simulated in its OWN knowledge base. Its facts are never
mixed with the real ones:
    - in the prompt they are in a separate section, marked hypothetical
    - on disk they are saved in a separate file next to the run:
        runs/run_<time>.json                                      real facts
        runs/run_<time>_alternatives/<object>_in_layer_<n>.json   one alternative branch
"""

from dataclasses import dataclass, field
from pathlib import Path

from .facts import Fact, layer_name
from .knowledge_base import KnowledgeBase
from .question import Question, tower_order
from .recorder import StackingRecorder
from .scoring import score_function_from_meta


@dataclass
class Evidence:
    question: Question
    facts: list[Fact] = field(default_factory=list)         # relevant facts of the real run
    hypothetical: list[Fact] = field(default_factory=list)  # facts of the simulated tower
    rule_names: list[str] = field(default_factory=list)     # rules that produced them
    notes: list[str] = field(default_factory=list)          # computed statements (plain text)
    alternative: KnowledgeBase | None = None                # the simulated tower, if any
    alternative_path: Path | None = None                    # file the alternative was saved to

    def add(self, kb: KnowledgeBase, fact_id: str, hypothetical: bool = False) -> None:
        """Add one fact (without its support chain)."""
        fact = kb.get(fact_id)
        target = self.hypothetical if hypothetical else self.facts
        if fact is None or fact in target:
            return
        target.append(fact)
        if fact.rule and fact.rule not in self.rule_names:
            self.rule_names.append(fact.rule)

    def add_all(self, kb: KnowledgeBase, facts, hypothetical: bool = False) -> None:
        for fact in facts:
            self.add(kb, fact.fact_id, hypothetical)


def collect_evidence(question: Question, kb: KnowledgeBase) -> Evidence:
    evidence = Evidence(question)
    evidence.notes.append('Actual tower (bottom -> top): ' + _tower_text(tower_order(kb)))
    evidence.add(kb, 'tower has_tower_stability')

    if question.type == 'why':
        _decision(evidence, kb, question.chosen, question.layer, against=None)
    elif question.type == 'why_not':
        _decision(evidence, kb, question.chosen, question.layer, against=question.alternative)
    elif question.type == 'what_if':
        _decision(evidence, kb, question.chosen, question.layer, against=question.alternative)
        _what_if(evidence, kb, question.alternative, question.layer)
    else:
        _basic(evidence, kb, question)
    return evidence


def _basic(evidence: Evidence, kb: KnowledgeBase, question: Question) -> None:
    """General question: the facts about the layer and objects it mentions."""
    if question.layer:
        evidence.add_all(kb, kb.facts(predicate='selected_in', layer=question.layer))
    for object_id in (question.chosen, question.alternative):
        if object_id:
            evidence.add_all(kb, kb.facts(object_id, 'selected_in'))
            evidence.add_all(kb, (f for f in kb.facts(object_id, 'is') if f.object in ('base', 'top')))
            evidence.add_all(kb, kb.facts(object_id, 'bigger_on_smaller'))
    if question.chosen and question.alternative:
        a, b = question.chosen, question.alternative
        evidence.add_all(kb, kb.facts(a, 'bigger_than', b) + kb.facts(b, 'bigger_than', a))


# ------------------------------------------------------------- the real run

def _decision(evidence: Evidence, kb: KnowledgeBase, chosen: str, layer: int,
              against: str | None) -> None:
    """Why `chosen` was placed in `layer` -- against one object, or all candidates."""
    selected = kb.get(f'L{layer}: {chosen} selected_in {layer_name(layer)}')
    if selected is None:                 # the question assumes something that did not happen
        really = tower_order(kb)
        evidence.notes.append(
            f'Note: {chosen} was NOT placed in layer {layer}; '
            f'{really[layer - 1]} was. {chosen} was placed in layer {really.index(chosen) + 1}.')
        return
    evidence.add(kb, selected.fact_id)
    evidence.add_all(kb, (f for f in kb.facts(chosen, 'is') if f.object in ('base', 'top')))

    preferences = kb.facts(chosen, 'preferred_over', layer=layer)
    if against is not None:
        preferences = [f for f in preferences if f.object == against]
        if not preferences:
            evidence.notes.append(f'Note: {against} was not a candidate in layer {layer} '
                                  f'(it was already placed below).')
        evidence.add_all(kb, kb.facts(against, 'selected_in'))     # where it really went
    evidence.add_all(kb, preferences)      # carry both objects' stability values

    others = {f.object for f in preferences} | ({against} if against else set())
    for other in others:
        evidence.add_all(kb, kb.facts(chosen, 'bigger_than', other) + kb.facts(other, 'bigger_than', chosen))


# --------------------------------------------------------- the imagined tower

def _what_if(evidence: Evidence, kb: KnowledgeBase, moved: str, layer: int) -> None:
    alternative = simulate(kb, forced_layer=layer, forced_id=moved)
    alternative.meta.update({
        'kind': 'hypothetical',
        'change': {'object': moved, 'layer': layer},
        'based_on': str(kb.path) if kb.path else None,
    })
    evidence.alternative = alternative
    if kb.path is not None:          # real run comes from a file -> keep the branch next to it
        evidence.alternative_path = alternative.save(alternative_path(kb.path, moved, layer))
    alt = tower_order(alternative)

    evidence.notes.append(
        f'Hypothetical change: {moved} is put in layer {layer} by assumption, '
        f'not because the robot would choose it there.')
    evidence.notes.append('Alternative tower (bottom -> top): ' + _tower_text(alt))

    actual_stability = kb.value('tower', 'has_tower_stability')
    alt_stability = alternative.value('tower', 'has_tower_stability')
    if actual_stability is not None and alt_stability is not None:
        change_word = ('lower' if alt_stability < actual_stability else
                       'higher' if alt_stability > actual_stability else 'the same')
        evidence.notes.append(f'Tower stability: actual = {actual_stability}, alternative = '
                              f'{alt_stability} (1.0 = ideal), so the alternative is {change_word}.')

    # Only what makes the alternative different: objects sitting on smaller ones.
    for n, object_id in enumerate(alt, start=1):
        local = alternative.value(object_id, 'has_local_stability', layer=n)
        if local is not None and local < 1.0:
            evidence.notes.append(
                f'In the alternative tower {object_id} sits on the smaller {alt[n - 2]}: '
                f'local stability {local}.')
    evidence.add_all(alternative, alternative.facts(predicate='bigger_on_smaller'), hypothetical=True)


def simulate(kb: KnowledgeBase, forced_layer: int, forced_id: str) -> KnowledgeBase:
    """Rebuild the tower with `forced_id` placed in `forced_layer`.

    - Layers below BOTH the forced layer and the object's real layer keep
      their real choice (nothing there needs to change).
    - The forced layer gets `forced_id`.
    - Every other layer is chosen again by the same greedy algorithm,
      with `forced_id` reserved for its forced layer.
    """
    score_function = score_function_from_meta(kb.meta)
    recorder = StackingRecorder(score_function=score_function)
    recorder.record_objects(list(kb.objects.values()))

    actual = tower_order(kb)
    real_layer = actual.index(forced_id) + 1 if forced_id in actual else forced_layer
    keep_until = min(forced_layer, real_layer) - 1

    remaining = list(kb.objects)
    for layer in range(1, len(kb.objects) + 1):
        if layer <= keep_until:
            chosen = actual[layer - 1]
        elif layer == forced_layer:
            chosen = forced_id
        else:
            tower = [kb.objects[i] for i in recorder.tower]
            candidates = [kb.objects[i] for i in remaining]
            free = [i for i in remaining if i != forced_id]
            chosen = max(free, key=lambda i: score_function(kb.objects[i], tower, candidates))
        recorder.record_layer(layer, list(remaining), chosen)
        remaining.remove(chosen)
    return recorder.kb


# ----------------------------------------------------------------- helpers

def alternative_path(run_path: Path, object_id: str, layer: int) -> Path:
    """runs/run_X.json -> runs/run_X_alternatives/<object>_in_layer_<n>.json"""
    run_path = Path(run_path)
    return run_path.parent / f'{run_path.stem}_alternatives' / f'{object_id}_in_layer_{layer}.json'


def _tower_text(tower: list[str]) -> str:
    return ', '.join(f'layer {n}: {object_id}' for n, object_id in enumerate(tower, start=1))
