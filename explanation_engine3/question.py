"""Stage 1: understand the question.

Question types (the first three get a focused explanation):

    why       "Why was the red cube placed in the base?"
              chosen = red cube, layer = 1
    why_not   "Why the red cube instead of the green cube in the base?"
              chosen = red cube, alternative = green cube, layer = 1
    what_if   "What if we choose the blue cube instead of the red cube for the base?"
              alternative = blue cube, layer = 1, chosen = the cube really placed there
    other     any other question about the tower ("Which cube is in the base?")
              answered from the basic facts: tower order, stability, and the
              objects / layer the question mentions

The LLM extracts these fields (handles any wording and typos); the result is
checked against the knowledge base and completed from the recorded run.
Without an LLM, or if its reply is unusable, a keyword extractor is used.
"""

import difflib
import json
import re
from dataclasses import dataclass

from .knowledge_base import KnowledgeBase

QUESTION_TYPES = ('why', 'why_not', 'what_if', 'other')

WHAT_IF_WORDS = ('what if', 'what would happen', 'what will happen', 'what happens if',
                 'suppose', 'imagine')
WHY_NOT_WORDS = ('instead of', 'rather than', 'why not', 'and not', 'over the')
BASE_WORDS = ('base', 'bottom', 'first layer', 'lowest')
TOP_WORDS = ('top', 'last layer', 'highest')


@dataclass
class Question:
    text: str
    type: str | None = None
    chosen: str | None = None          # the object the robot placed (or is asked about)
    alternative: str | None = None     # the other object (why_not / what_if)
    layer: int | None = None
    extracted_by: str = 'keywords'     # 'llm' or 'keywords'

    def __str__(self) -> str:
        return (f'type={self.type} chosen={self.chosen} alternative={self.alternative} '
                f'layer={self.layer} (by {self.extracted_by})')


def parse_question(text: str, kb: KnowledgeBase, llm=None) -> Question:
    question = None
    if llm is not None:
        try:
            question = llm_extract(text, kb, llm)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            question = None                   # fall back to keywords
    if question is None or question.type is None:
        question = keyword_extract(text, kb)
    complete_from_run(question, kb)
    _check(question)
    return question


# --------------------------------------------------------------------- LLM stage

def llm_extract(text: str, kb: KnowledgeBase, llm) -> Question:
    system = '\n'.join([
        'You read a question about a tower of objects built by a robot. Reply with JSON only:',
        '{"type": ..., "chosen": id or null, "alternative": id or null, "layer": number or null}',
        'type:',
        '- "why":     why was an object placed where it is (e.g. "why is the red cube in the base?")',
        '- "why_not": why one object and not another (e.g. "why red instead of green?", "why not green?")',
        '- "what_if": what would happen with another object (e.g. "what if blue instead of red?")',
        '- "other":   any other question (e.g. "which cube is in the base?", "is the tower stable?")',
        'chosen: the object the robot placed / the question asks about '
        '(for what_if: the object that would be replaced).',
        'alternative: the other object (why_not: the one not chosen; what_if: the one imagined; '
        'other: a second object if mentioned). null for "why".',
        'layer: 1 = base/bottom; "top" = the last layer; null if not said.',
        'Use only ids from the list. Fix spelling mistakes in the question.',
    ])
    user = '\n'.join([
        'OBJECTS (id: colour shape):',
        *[f'- {e.element_id}: {e.color} {e.shape}' for e in kb.objects.values()],
        'ACTUAL TOWER:',
        *[f'- layer {n}: {object_id}' for n, object_id in enumerate(tower_order(kb), start=1)],
        f'QUESTION: {text}',
    ])
    reply = json.loads(llm.chat(system, user, json_mode=True))

    question = Question(text, extracted_by='llm')
    question.type = reply.get('type') if reply.get('type') in QUESTION_TYPES else None
    question.chosen = reply.get('chosen') if reply.get('chosen') in kb.objects else None
    question.alternative = reply.get('alternative') if reply.get('alternative') in kb.objects else None
    layer = reply.get('layer')
    question.layer = int(layer) if layer is not None and 1 <= int(layer) <= len(tower_order(kb)) else None
    return question


# ---------------------------------------------------------------- keyword stage

def keyword_extract(text: str, kb: KnowledgeBase) -> Question:
    lower = text.lower()
    question = Question(text, extracted_by='keywords')
    mentioned = _objects_in_order(lower, kb)
    question.layer = _layer_in(lower, kb)

    if any(word in lower for word in WHAT_IF_WORDS):
        question.type = 'what_if'                           # "what if Y instead of X"
        question.alternative = mentioned[0] if mentioned else None
        question.chosen = mentioned[1] if len(mentioned) > 1 else None
    elif any(word in lower for word in WHY_NOT_WORDS):
        question.type = 'why_not'
        if 'why not' in lower and len(mentioned) == 1:      # "why not Y?"
            question.alternative = mentioned[0]
        else:                                               # "why X instead of Y"
            question.chosen = mentioned[0] if mentioned else None
            question.alternative = mentioned[1] if len(mentioned) > 1 else None
    elif 'why' in lower:
        question.type = 'why'
        question.chosen = mentioned[0] if mentioned else None
    else:
        question.type = 'other'
        question.chosen = mentioned[0] if mentioned else None
        question.alternative = mentioned[1] if len(mentioned) > 1 else None
    return question


def _objects_in_order(lower: str, kb: KnowledgeBase) -> list[str]:
    """Object ids mentioned in the text, in the order they appear.
    Colours tolerate small typos ('geen' -> green)."""
    hits = []                                   # (position, object_id)
    words = [(match.start(), match.group()) for match in re.finditer(r'[a-z]+', lower)]
    for element in kb.objects.values():
        names = [element.element_id, element.element_id.replace('_', ' '), element.color]
        position = next((lower.find(name.lower()) for name in names
                         if name != 'unknown' and lower.find(name.lower()) >= 0), -1)
        if position < 0 and element.color != 'unknown':
            position = next((start for start, word in words
                             if difflib.get_close_matches(word, [element.color], cutoff=0.75)), -1)
        if position >= 0:
            hits.append((position, element.element_id))
    return [object_id for _, object_id in sorted(hits)]


def _layer_in(lower: str, kb: KnowledgeBase) -> int | None:
    match = re.search(r'layer\s*(\d+)', lower)
    if match:
        return int(match.group(1))
    if any(word in lower for word in BASE_WORDS):
        return 1
    if any(word in lower for word in TOP_WORDS) and tower_order(kb):
        return len(tower_order(kb))
    return None


# ---------------------------------------------------- fill gaps from the run

def complete_from_run(question: Question, kb: KnowledgeBase) -> None:
    """Fill what the question leaves implicit, using what really happened."""
    tower = tower_order(kb)

    def layer_of(object_id):
        return tower.index(object_id) + 1 if object_id in tower else None

    if question.type in ('why', 'why_not') and question.layer is None:
        # why X? -> where X is.  why not Y? (no X, no layer) -> the base.
        question.layer = layer_of(question.chosen) if question.chosen else 1
    if question.type == 'what_if' and question.layer is None and question.chosen:
        question.layer = layer_of(question.chosen)        # "Y instead of X" -> X's layer

    if question.type != 'other' and question.layer and question.layer <= len(tower):
        placed_there = tower[question.layer - 1]
        if question.type == 'what_if' or question.chosen is None:
            question.chosen = placed_there


def _check(question: Question) -> None:
    if question.type in (None, 'other'):
        return                  # general question: answered from the basic facts
    if question.chosen is None or question.layer is None:
        raise ValueError(f'Could not tell which object or layer the question is about: {question}')
    if question.type in ('why_not', 'what_if') and question.alternative is None:
        raise ValueError(f'Could not tell which other object the question compares with: {question}')


def tower_order(kb: KnowledgeBase) -> list[str]:
    """Object ids from bottom to top."""
    selections = sorted(kb.facts(predicate='selected_in'), key=lambda fact: fact.layer)
    return [fact.subject for fact in selections]
