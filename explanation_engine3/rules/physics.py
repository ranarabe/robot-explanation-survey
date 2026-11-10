"""Physics rules: facts that are true by the laws of the world."""

from .base import conclude, rule


@rule('under', source='physics',
      if_text='Y on_top_of Z',
      then_text='Z under Y')
def under(kb):
    for fact in kb.facts(predicate='on_top_of'):
        yield conclude(fact.object, 'under', fact.subject, premises=[fact])


@rule('bigger_than', source='physics',
      if_text='Y.volume > X.volume',
      then_text='Y bigger_than X')
def bigger_than(kb):
    # Reads numbers from the object info, not from facts.
    for y in kb.objects.values():
        for x in kb.objects.values():
            if y.volume > x.volume:
                yield conclude(y.element_id, 'bigger_than', x.element_id,
                               evidence={f'{y.element_id}.volume': y.volume,
                                         f'{x.element_id}.volume': x.volume})


@rule('smaller_than', source='physics',
      if_text='Y bigger_than X',
      then_text='X smaller_than Y')
def smaller_than(kb):
    for fact in kb.facts(predicate='bigger_than'):
        yield conclude(fact.object, 'smaller_than', fact.subject, premises=[fact])


@rule('bigger_from_smaller', source='physics',
      if_text='Y smaller_than X',
      then_text='X bigger_than Y')
def bigger_from_smaller(kb):
    # Mirror of smaller_than. Usually adds nothing new (duplicates are
    # ignored), but keeps the relation symmetric if a smaller_than fact
    # is ever given directly.
    for fact in kb.facts(predicate='smaller_than'):
        yield conclude(fact.object, 'bigger_than', fact.subject, premises=[fact])


@rule('bigger_on_smaller', source='physics',
      if_text='Y on_top_of Z AND Y bigger_than Z',
      then_text='Y bigger_on_smaller Z (Y is bigger than Z but placed on top of it: '
                'this breaks the order "bigger objects go lower")')
def bigger_on_smaller(kb):
    for on_top in kb.facts(predicate='on_top_of'):
        bigger = kb.get(f'{on_top.subject} bigger_than {on_top.object}')
        if bigger is not None:
            yield conclude(on_top.subject, 'bigger_on_smaller', on_top.object,
                           premises=[on_top, bigger])


RULES = [under, bigger_than, smaller_than, bigger_from_smaller, bigger_on_smaller]
