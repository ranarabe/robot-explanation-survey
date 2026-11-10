"""Step 3: build the text given to the LLM.

The prompt contains ONLY:
    - the environment (static facts)
    - the algorithm (its description, its rules, the score function)
    - the objects involved
    - the facts and rules relevant to this question (from evidence.py)
    - computed results (e.g. the simulated what-if tower)
and tells the LLM to answer from these and nothing else.
"""

import re

from .evidence import Evidence
from .knowledge_base import KnowledgeBase
from .rules import ALGORITHM
from .scoring import score_function_from_meta

# Edit these lists to tune how strictly the LLM sticks to the knowledge base.
GROUNDING_RULES = [
    'Every statement in your answer must come from the FACTS, RULES, '
    'ALGORITHM, ENVIRONMENT or COMPUTED RESULTS given below.',
    'Do not add any information of your own: no general knowledge, no assumptions, '
    'no properties that are not listed (for example mass, weight, material, friction or balance).',
    'Do not speculate. Do not use words like "might", "may", "could" or "probably" '
    'unless the given information says so.',
    'Use only the numbers that appear below; do not compute or estimate new ones.',
    'If the given information does not answer the question, say exactly what is missing '
    'instead of guessing.',
    # Current criterion.
    'The robot decides with STABILITY values computed from VOLUMES only (see ALGORITHM). '
    'Explain with these stability values. Do not talk about weight, balance, falling or '
    'collapse: there is no such information.',
]
WHAT_IF_RULES = [
    'Facts marked "hypothetical" describe a tower that was NOT built; describe them as '
    'what would happen, never as what happened.',
    'Focus on the consequence of the change: how the tower stability would change '
    'compared with the tower the robot built.',
    'Do not describe where the other objects would go or which object would sit on which, '
    'unless the question asks about them.',
]

# ------------------------------------------------------------- reader and length

USER_TYPES = {
    'ordinary': (
        'The reader is NOT technical. Use simple everyday words only. '
        'Never write technical words (score, algorithm, rule, fact, layer, candidate, '
        'local stability, global stability, parameter, metric), object ids, decimal numbers, '
        'units or formulas. Describe sizes and stability with words '
        '(bigger, smaller, steadier, the steadiest tower, less steady). '
        'Explain the idea, not the calculation.'
    ),
    'expert': (
        'The reader is an expert. Use precise technical language: name the algorithm, '
        'the rules, local stability, global stability, tower stability and the score, '
        'and quote the numbers given.'
    ),
}
LENGTHS = {
    'short': 'Answer in at most two sentences.',
    'long': 'Give a full explanation in two to four short paragraphs: first the decision, '
            'then the reasons step by step, then what it means for the tower.',
}

# Words/patterns an ordinary reader should not see. If the answer contains one,
# the LLM is asked once to rewrite it (see ask.py).
TECHNICAL_TERMS = [
    r'\bscores?\b', r'\balgorithms?\b', r'\bgreedy\b', r'\bheuristics?\b', r'\brules?\b',
    r'\bfacts?\b', r'\blayers?\b', r'\bcandidates?\b', r'\blocal stability\b',
    r'\bglobal stability\b', r'\btower stability\b', r'\bparameters?\b', r'\bmetrics?\b',
    r'\bm3\b', r'm³', r'\b\w+_\w+_\d+\b',     # units, ids like cube_red_37
    r'\b\d+\.\d+\b',                        # decimal numbers like 0.837677
]


def find_technical_terms(text: str) -> list[str]:
    found = []
    for pattern in TECHNICAL_TERMS:
        found += re.findall(pattern, text, flags=re.IGNORECASE)
    return sorted(set(found))


def rewrite_prompt(answer: str, terms: list[str]) -> tuple[str, str]:
    """(system, user) asking the LLM to remove technical language from an answer."""
    system = ('Rewrite the text for a reader who is not technical. Keep exactly the same '
              'meaning and do not add any information. ' + USER_TYPES['ordinary'])
    user = f'Remove these words: {", ".join(terms)}\n\nText:\n{answer}'
    return system, user


def build_prompt(evidence: Evidence, kb: KnowledgeBase,
                 user_type: str = 'ordinary', length: str = 'short') -> tuple[str, str]:
    """Return (system_prompt, user_prompt)."""
    question = evidence.question

    system = '\n'.join([
        'You explain the decisions of a robot arm that stacks objects into a tower.',
        '',
        'STRICT GROUNDING RULES (most important):',
        *[f'- {line}' for line in GROUNDING_RULES],
        *([f'- {line}' for line in WHAT_IF_RULES] if question.type == 'what_if' else []),
        '',
        'STYLE:',
        '- Object ids look like cube_red_37 (shape_colour_number). In the answer write '
        '"the red cube"; add the number only if two objects have the same colour.',
        f'- {USER_TYPES[user_type]}',
        f'- {LENGTHS[length]}',
        '- Answer in English.',
    ])

    sections = [
        # How the robot decides (short). Rules appear only in RULES USED.
        ('ALGORITHM', [ALGORITHM['description']] + score_function_from_meta(kb.meta).describe()),
        ('OBJECTS', [_object_line(kb, object_id) for object_id in _objects_in(evidence, kb)]),
        ('RELEVANT FACTS (what really happened)',
         [_fact_line(fact) for fact in evidence.facts if not kb.is_static(fact)]),
        ('FACTS OF THE ALTERNATIVE TOWER (hypothetical, did NOT happen)',
         [_fact_line(fact) for fact in evidence.hypothetical if not kb.is_static(fact)]),
        ('RULES USED', [str(r) for r in kb.rules if r.name in evidence.rule_names]),
        ('COMPUTED RESULTS', evidence.notes),
        ('QUESTION', [question.text]),
    ]
    user = '\n\n'.join(
        f'## {title}\n' + '\n'.join(f'- {line}' for line in lines)
        for title, lines in sections if lines
    )
    return system, user


def _objects_in(evidence: Evidence, kb: KnowledgeBase) -> list[str]:
    if evidence.alternative is not None or evidence.question.type == 'other':
        return list(kb.objects)                   # what_if / general question: all objects
    ids = []
    for fact in evidence.facts:
        for name in (fact.subject, fact.object):
            if name in kb.objects and name not in ids:
                ids.append(name)
    for name in (evidence.question.chosen, evidence.question.alternative):
        if name in kb.objects and name not in ids:
            ids.append(name)
    return ids


def _object_line(kb: KnowledgeBase, object_id: str) -> str:
    e = kb.objects[object_id]
    return (f'{object_id}: {e.width:.3f} x {e.depth:.3f} x {e.height:.3f} m, '
            f'volume {e.volume:.6g} m3')


def _fact_line(fact) -> str:
    line = f'{fact}   ({fact.source}'
    line += f', from rule {fact.rule})' if fact.rule else ', recorded)'
    if fact.evidence:
        line += '   values: ' + ', '.join(f'{k}={v}' for k, v in fact.evidence.items())
    return line
