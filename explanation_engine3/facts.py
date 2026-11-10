"""A fact is a triple:  Subject  Predicate  Object.

Two kinds, decided automatically by the object:

    relation fact   object is a name      cube_red_37  on_top_of  cube_blue_12
    value fact      object is a number    cube_red_37  has_score  0.82   (layer 1)

A value fact holds ONE value per (layer, subject, predicate): adding it
again replaces the old value. A relation fact is unique as a whole triple.

Every fact also remembers WHERE it came from:
    source    -> environment / physics / algorithm / execution
    rule      -> name of the rule that inferred it (None = not inferred)
    premises  -> ids of the facts the rule used
    evidence  -> numbers the rule used (e.g. volumes)

The premises make "why?" answers possible: we follow them backwards.
"""

from dataclasses import asdict, dataclass, field


SOURCES = ('environment', 'physics', 'algorithm', 'execution')


def layer_name(layer: int) -> str:
    return f'layer_{layer}'


def tidy_number(value):
    """Round floats to 6 significant digits (removes 0.000343000000001 noise)."""
    if isinstance(value, float):
        return float(f'{value:.6g}')
    return value


@dataclass
class Fact:
    subject: str
    predicate: str
    object: str | float
    source: str | None = None
    layer: int | None = None
    rule: str | None = None
    premises: list[str] = field(default_factory=list)
    evidence: dict = field(default_factory=dict)

    def __post_init__(self):
        self.object = tidy_number(self.object)
        self.evidence = {key: tidy_number(value) for key, value in self.evidence.items()}

    @property
    def is_value(self) -> bool:
        return isinstance(self.object, (int, float)) and not isinstance(self.object, bool)

    @property
    def is_inferred(self) -> bool:
        return self.rule is not None

    @property
    def fact_id(self) -> str:
        """Readable unique id.

        relation: 'L1: cube_red_37 selected_in layer_1'
        value:    'L1: cube_red_37 has_score'        (the number is not part of the id)
        """
        text = f'{self.subject} {self.predicate}'
        if not self.is_value:
            text += f' {self.object}'
        if self.layer is not None:
            text = f'L{self.layer}: {text}'
        return text

    def __str__(self) -> str:
        if self.is_value:
            return f'{self.fact_id} = {self.object}'
        return self.fact_id

    def to_dict(self) -> dict:
        data = {'id': self.fact_id, **asdict(self)}
        # Keep the JSON short: drop empty provenance fields.
        for key in ('layer', 'rule'):
            if data[key] is None:
                del data[key]
        for key in ('premises', 'evidence'):
            if not data[key]:
                del data[key]
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'Fact':
        data = {key: value for key, value in data.items() if key != 'id'}
        return cls(**data)
