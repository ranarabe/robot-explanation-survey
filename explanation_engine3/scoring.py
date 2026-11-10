"""Score functions: how good is a candidate for the next layer?

Every score function is called the same way so they can be swapped:

    score(candidate, tower, remaining) -> float

    candidate  Element being evaluated
    tower      Elements already placed, bottom -> top
    remaining  Elements not placed yet (candidate included)

Higher score = better choice for the current layer.

Current policy: tower stability computed from VOLUMES only.
"""

from .objects import Element


# --------------------------------------------------------------- stability measures

def local_stability(candidate: Element, tower: list[Element]) -> float:
    """Local stability: how well the candidate sits on the current top of the tower.
    1.0 if it is not bigger than the object below it (or it is on the table);
    otherwise volume_below / volume_candidate (smaller = worse)."""
    if not tower:
        return 1.0
    return min(1.0, tower[-1].volume / candidate.volume)


def tower_stability(tower: list[Element]) -> float:
    """Global (tower) stability of a complete tower, from 0 to 1.
    Lower layers weigh more: sum((N - i) * volume_i), divided by the same sum for the
    ideal order (biggest at the bottom). 1.0 = ideal order."""
    def weighted(order):
        n = len(order)
        return sum((n - i) * element.volume for i, element in enumerate(order))

    ideal = sorted(tower, key=lambda element: element.volume, reverse=True)
    return weighted(tower) / weighted(ideal)


def global_stability(candidate: Element, tower: list[Element], remaining: list[Element]) -> float:
    """Global stability of a candidate: stability of the best tower that can still be
    built after choosing it (the rest placed biggest-first)."""
    rest = sorted((e for e in remaining if e is not candidate),
                  key=lambda element: element.volume, reverse=True)
    return tower_stability(tower + [candidate] + rest)


# -------------------------------------------------------------------- score functions

class StabilityScore:
    """score = global stability (bigger objects go lower).

    Local stability is computed and recorded too, so it can be used in
    explanations, but it does not decide.
    """

    name = 'stability_score'
    weights = {}            # no weights in this version

    def components(self, candidate, tower, remaining) -> dict:
        """Values recorded as facts for every candidate."""
        return {
            'has_local_stability': local_stability(candidate, tower),
            'has_global_stability': global_stability(candidate, tower, remaining),
        }

    def __call__(self, candidate, tower, remaining) -> float:
        return global_stability(candidate, tower, remaining)

    def describe(self) -> list[str]:
        return [
            'Score = global stability of the candidate. The candidate with the highest '
            'score is placed, so bigger objects go lower.',
            'Global stability of a candidate: ' + _first_paragraph(global_stability),
            'Tower stability: ' + _first_paragraph(tower_stability),
            'Local stability (recorded for explanation, does not decide): '
            + _first_paragraph(local_stability),
        ]


def volume_score(candidate: Element, tower: list[Element], remaining: list[Element]) -> float:
    """The bigger the volume, the lower it goes."""
    return candidate.volume


volume_score.name = 'volume_score'
volume_score.weights = {}
volume_score.describe = lambda: ['Score = volume of the object. ' + volume_score.__doc__]


# ------------------------------------------------------------------------- registry

# name -> factory(weights). The run file stores the name and weights, so the
# what-if simulator can rebuild exactly the same function later.
SCORE_FUNCTIONS = {
    'stability_score': lambda weights: StabilityScore(),     # old runs had weights: ignored
    'volume_score': lambda weights: volume_score,
}

DEFAULT_SCORE_FUNCTION = StabilityScore()


def score_function_from_meta(meta: dict):
    factory = SCORE_FUNCTIONS.get(meta.get('score_function'))
    if factory is None:
        return DEFAULT_SCORE_FUNCTION
    return factory(meta.get('score_weights', {}))


def _first_paragraph(function) -> str:
    return ' '.join((function.__doc__ or '').split())
