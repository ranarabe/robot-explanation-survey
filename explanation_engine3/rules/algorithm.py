"""Algorithm rules: what the ordering algorithm means.

If the ordering algorithm changes, only this file should change.
Current algorithm: greedy -- at each layer pick the candidate with the
highest score (score facts are recorded by the planner as execution facts).
"""

from ..facts import layer_name
from .base import conclude, rule

# Saved in every run file. Increase the version whenever these rules change,
# so old runs can be recognised.
ALGORITHM = {
    'name': 'greedy_stability',
    'version': 3,
    'description': (
        'Greedy stacking: the tower is built from the bottom up. At each layer the '
        'algorithm gives every object that is not placed yet a score, its global '
        'stability, and places the one with the highest score. A decision is never revisited.'
    ),
}


# Value facts recorded per candidate and layer (see recorder.py).
SCORE_PREDICATES = ('has_local_stability', 'has_global_stability', 'has_score')


@rule('placed', source='algorithm',
      if_text='Y selected_in any layer',
      then_text='Y is placed')
def placed(kb):
    for fact in kb.facts(predicate='selected_in'):
        yield conclude(fact.subject, 'is', 'placed', premises=[fact])


@rule('candidate_in', source='algorithm',
      if_text='layer_n has a selection AND X not selected in any layer < n',
      then_text='X candidate_in layer_n')
def candidate_in(kb):
    for selection in kb.facts(predicate='selected_in'):
        n = selection.layer
        placed_before = {f.subject for f in kb.facts(predicate='selected_in')
                         if f.layer < n}
        for object_id in kb.objects:
            if object_id not in placed_before:
                yield conclude(object_id, 'candidate_in', layer_name(n),
                               layer=n, premises=[selection])


@rule('best_candidate', source='algorithm',
      if_text='Y selected_in layer_n',
      then_text='Y best_candidate_in layer_n')
def best_candidate(kb):
    for fact in kb.facts(predicate='selected_in'):
        yield conclude(fact.subject, 'best_candidate_in', fact.object,
                       layer=fact.layer, premises=[fact])


@rule('preferred_over', source='algorithm',
      if_text='Y best_candidate_in layer_n AND X candidate_in layer_n AND X != Y',
      then_text='Y preferred_over X (in layer_n)')
def preferred_over(kb):
    for best in kb.facts(predicate='best_candidate_in'):
        n = best.layer
        for other in kb.facts(predicate='candidate_in', layer=n):
            if other.subject == best.subject:
                continue
            evidence = {}
            for object_id in (best.subject, other.subject):
                for predicate in SCORE_PREDICATES:
                    value = kb.value(object_id, predicate, layer=n)
                    if value is not None:
                        evidence[f'{object_id}.{predicate.removeprefix("has_")}'] = value
            yield conclude(best.subject, 'preferred_over', other.subject,
                           layer=n, premises=[best, other], evidence=evidence)


RULES = [placed, candidate_in, best_candidate, preferred_over]
