"""Environment rules: how the tower is arranged in space."""

from .base import conclude, rule


@rule('on_top_of', source='environment',
      if_text='Y selected_in layer_n AND Z selected_in layer_(n-1)',
      then_text='Y on_top_of Z')
def on_top_of(kb):
    for upper in kb.facts(predicate='selected_in'):
        for lower in kb.facts(predicate='selected_in', layer=upper.layer - 1):
            yield conclude(upper.subject, 'on_top_of', lower.subject,
                           premises=[upper, lower])


@rule('on_table', source='environment',
      if_text='Y selected_in layer_1 AND layer_1 rests_on S',
      then_text='Y on_top_of S')
def on_table(kb):
    # Uses a static fact from knowledge/environment.json.
    for support in kb.facts(subject='layer_1', predicate='rests_on'):
        for fact in kb.facts(predicate='selected_in', layer=1):
            yield conclude(fact.subject, 'on_top_of', support.object,
                           premises=[fact, support])


@rule('is_base', source='environment',
      if_text='Y selected_in layer_1',
      then_text='Y is base')
def is_base(kb):
    for fact in kb.facts(predicate='selected_in', layer=1):
        yield conclude(fact.subject, 'is', 'base', premises=[fact])


@rule('is_top', source='environment',
      if_text='all objects placed AND Y selected_in the last layer',
      then_text='Y is top')
def is_top(kb):
    placed = kb.facts(predicate='selected_in')
    if not placed or len(placed) < len(kb.objects):
        return  # tower not finished yet
    last = max(fact.layer for fact in placed)
    for fact in kb.facts(predicate='selected_in', layer=last):
        yield conclude(fact.subject, 'is', 'top', premises=[fact])


RULES = [on_top_of, on_table, is_base, is_top]
