"""Records what the ordering code does, as execution facts.

The planner calls this while it builds the tower:

    recorder = StackingRecorder()
    recorder.record_objects(elements)
    recorder.record_layer(1, candidate_ids=[...], selected_id='cube_red_37')
    recorder.record_layer(2, ...)
    path = recorder.save()

For every layer it records, for every candidate:
    L<n>: <candidate> has_local_stability  <value>
    L<n>: <candidate> has_global_stability <value>
    L<n>: <candidate> has_score            <value>
and then
    L<n>: <selected>  selected_in layer_<n>
When the tower is complete:
    tower has_tower_stability <value>
The rules then infer candidate_in, preferred_over, on_top_of, ...
"""

from .facts import layer_name
from .knowledge_base import KnowledgeBase
from .objects import Element
from .scoring import DEFAULT_SCORE_FUNCTION, tower_stability


class StackingRecorder:

    def __init__(self, score_function=DEFAULT_SCORE_FUNCTION, kb: KnowledgeBase | None = None):
        self.kb = kb or KnowledgeBase()
        self.score_function = score_function
        self.tower: list[str] = []          # ids placed so far, bottom -> top
        self.kb.meta['score_function'] = score_function.name
        self.kb.meta['score_weights'] = dict(score_function.weights)

    def record_objects(self, elements: list[Element]) -> None:
        for element in elements:
            self.kb.add_object(element)

    def record_layer(self, layer: int, candidate_ids: list[str], selected_id: str) -> str | None:
        """Record one decision. Returns a warning text if the planner's choice
        is not the best-scoring candidate (the trace would then disagree)."""
        tower = [self.kb.objects[i] for i in self.tower]
        remaining = [self.kb.objects[i] for i in candidate_ids]

        scores = {}
        for candidate in remaining:
            if hasattr(self.score_function, 'components'):
                parts = self.score_function.components(candidate, tower, remaining)
                for predicate, value in parts.items():
                    self.kb.add_fact(candidate.element_id, predicate, value,
                                     source='execution', layer=layer)
            scores[candidate.element_id] = self.score_function(candidate, tower, remaining)
            self.kb.add_fact(candidate.element_id, 'has_score', scores[candidate.element_id],
                             source='execution', layer=layer)

        self.kb.add_fact(selected_id, 'selected_in', layer_name(layer),
                         source='execution', layer=layer)
        self.tower.append(selected_id)

        if len(self.tower) == len(self.kb.objects):
            final = tower_stability([self.kb.objects[i] for i in self.tower])
            self.kb.add_fact('tower', 'has_tower_stability', final, source='execution')

        best_id = max(scores, key=scores.get)
        if scores[selected_id] < scores[best_id]:
            return (f'layer {layer}: planner selected {selected_id} '
                    f'(score {scores[selected_id]:.6g}) but {best_id} scores higher '
                    f'({scores[best_id]:.6g}) with {self.score_function.name}')
        return None

    def save(self, path=None):
        return self.kb.save(path)
