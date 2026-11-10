"""Ask a question about the last stacking run.

    ros2 run explanation_engine3 ask3          (interactive: type questions, empty line to quit)
    ros2 run explanation_engine3 ask3 "Why was the red cube chosen for the base?"
    ros2 run explanation_engine3 ask3 --user expert --length long

Options:
    --user               ordinary (default) | expert   (ordinary: no technical words)
    --length             short (default) | long
    --run FILE           run file (default: the latest in src/explanation_engine3/runs)
    --show-facts         print how the question was understood and the facts used
    --show-prompt        print everything sent to the LLM (instructions included)
    --llm BACKEND        openai (default) | ollama | none
    --no-llm             same as --llm none (shows the prompt only)
    --model NAME         model name (openai: $OPENAI_MODEL or gpt-6-astra, ollama: qwen3:8b)

OpenAI needs the API key in the environment:
    export OPENAI_API_KEY="sk-..."
Test the key:  ros2 run explanation_engine3 check_openai
"""

import argparse

from .evidence import collect_evidence
from .knowledge_base import KnowledgeBase, latest_run
from .llm import make_llm
from .prompt import LENGTHS, USER_TYPES, build_prompt, find_technical_terms, rewrite_prompt
from .question import parse_question


def answer(text, kb, llm=None, user_type='ordinary', length='short'):
    """Full pipeline.
    Returns (question, system_prompt, user_prompt, removed_terms, answer_or_None);
    removed_terms lists technical words the ordinary-reader rewrite removed."""
    question = parse_question(text, kb, llm)
    evidence = collect_evidence(question, kb)
    if evidence.alternative_path:
        print(f'[alternative branch saved to {evidence.alternative_path}]')
    system, user = build_prompt(evidence, kb, user_type, length)
    reply = llm.chat(system, user) if llm else None

    # An ordinary reader must not see technical words: rewrite once if needed.
    terms = []
    if reply and user_type == 'ordinary':
        terms = find_technical_terms(reply)
        if terms:
            reply = llm.chat(*rewrite_prompt(reply, terms))
    return question, system, user, terms, reply


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('question', nargs='?', default=None)
    parser.add_argument('--user', choices=USER_TYPES, default='ordinary')
    parser.add_argument('--length', choices=LENGTHS, default='short')
    parser.add_argument('--run', default=None)
    parser.add_argument('--show-facts', action='store_true')
    parser.add_argument('--show-prompt', action='store_true')
    parser.add_argument('--llm', choices=['openai', 'ollama', 'none'], default='openai')
    parser.add_argument('--no-llm', action='store_true')
    parser.add_argument('--model', default=None)
    args = parser.parse_args()

    kb = KnowledgeBase.load(args.run or latest_run())
    try:
        llm = make_llm('none' if args.no_llm else args.llm, args.model)
    except RuntimeError as error:
        raise SystemExit(f'[error] {error}') from None

    user_type, length = args.user, args.length
    print(f'[reader: {user_type}, length: {length}]')

    questions = [args.question] if args.question else _typed_questions(kb)
    for text in questions:
        try:
            question, system, user, removed, reply = answer(text, kb, llm, user_type, length)
        except (ValueError, RuntimeError) as error:
            print(f'[error] {error}\n')
            continue
        if args.show_prompt or reply is None:
            print(f'[understood] {question}\n')
            print('==== SYSTEM ====\n' + system + '\n\n==== USER ====\n' + user + '\n')
        elif args.show_facts:
            _print_facts(question, user)
        if reply is not None:
            if args.show_facts and removed:
                print(f'(answer rewritten for an ordinary reader; removed: {", ".join(removed)})')
            print(('==== ANSWER ====\n' if args.show_facts else '\n') + reply + '\n')


FACT_SECTIONS = ('RELEVANT FACTS', 'FACTS OF THE ALTERNATIVE TOWER', 'RULES USED', 'COMPUTED RESULTS')


def _print_facts(question, user_prompt: str) -> None:
    """Print the understood question and only the fact sections of the prompt."""
    print(f'\n==== UNDERSTOOD ====\n{question}\n')
    for section in user_prompt.split('\n\n'):
        if section.startswith('## ') and section[3:].startswith(FACT_SECTIONS):
            print(section.replace('## ', '==== ', 1) + '\n')


def _typed_questions(kb):
    print('Objects in this run: ' + ', '.join(kb.objects))
    print('Type a question (empty line to quit).')
    while True:
        try:
            text = input('\n? ').strip()
        except EOFError:
            return
        if not text:
            return
        yield text


if __name__ == '__main__':
    main()
