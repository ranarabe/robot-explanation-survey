"""Demo without ROS: three cubes recorded exactly like stack_planner does.

Run:  python3 -m explanation_engine3.demo [output.json]
(default output: src/explanation_engine3/runs/run_<time>.json)
"""

import sys

from .objects import Element
from .recorder import StackingRecorder


def main():
    cubes = [
        Element('cube_green_1', 'cube', 'green', 0.05, 0.05, 0.05, detection_id=1),
        Element('cube_red_2', 'cube', 'red', 0.07, 0.07, 0.07, detection_id=2),
        Element('cube_blue_3', 'cube', 'blue', 0.04, 0.04, 0.04, detection_id=3),
    ]
    # Same ordering as stack_planner.py: biggest volume at the bottom.
    ordered = sorted(cubes, key=lambda cube: cube.volume, reverse=True)

    recorder = StackingRecorder()
    recorder.record_objects(cubes)
    remaining = [cube.element_id for cube in cubes]
    for layer, cube in enumerate(ordered, start=1):
        warning = recorder.record_layer(layer, list(remaining), cube.element_id)
        if warning:
            print('WARNING:', warning)
        remaining.remove(cube.element_id)
    kb = recorder.kb

    print('Tower (bottom -> top):', ' -> '.join(cube.element_id for cube in ordered))
    print('Tower stability:', kb.value('tower', 'has_tower_stability'))
    for layer in kb.layers():
        print(f'\nLayer {layer}:')
        for fact in kb.facts(layer=layer, inferred=False):
            print(f'   {fact}')

    print('\nWhy is the red cube preferred over the green cube for the base?')
    print('\n'.join(kb.trace('L1: cube_red_2 preferred_over cube_green_1')))

    path = recorder.save(sys.argv[1] if len(sys.argv) > 1 else None)
    print(f'\nSaved to {path}')


if __name__ == '__main__':
    main()
