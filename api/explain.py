import json
import os
import traceback
from pathlib import Path
from http.server import BaseHTTPRequestHandler

from explanation_engine3.evidence import collect_evidence
from explanation_engine3.knowledge_base import KnowledgeBase
from explanation_engine3.llm import OpenAILLM
from explanation_engine3.prompt import build_prompt, find_technical_terms, rewrite_prompt
from explanation_engine3.question import parse_question


ROOT = Path(__file__).resolve().parents[1]
RUN_FILE = ROOT / 'data' / 'explanation-run.json'
PACKAGE_DIR = ROOT / 'explanation_engine3' / 'knowledge'
MAX_QUESTIONS = 5
question_counts = {}
knowledge_base = None


def get_knowledge_base():
    global knowledge_base
    if knowledge_base is None:
        knowledge_base = KnowledgeBase.load(RUN_FILE, static_dir=PACKAGE_DIR)
        # Vercel Function filesystems are read-only. Counterfactual questions
        # may otherwise try to save an alternative-run JSON beside the source run.
        knowledge_base.path = None
    return knowledge_base


def answer_question(question_text):
    llm = OpenAILLM(model=os.environ.get('OPENAI_MODEL'))
    kb = get_knowledge_base()
    question = parse_question(question_text, kb, llm)
    evidence = collect_evidence(question, kb)
    system, user = build_prompt(evidence, kb, 'ordinary', 'short')
    answer = llm.chat(system, user)
    terms = find_technical_terms(answer)
    if terms:
        answer = llm.chat(*rewrite_prompt(answer, terms))
    return answer


class handler(BaseHTTPRequestHandler):
    def _send(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(204, {})

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', '0'))
            payload = json.loads(self.rfile.read(length).decode('utf-8'))
            question = str(payload.get('question', '')).strip()
            participant_id = str(payload.get('participantId', '')).strip() or 'anonymous'
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
            self._send(400, {'error': 'Invalid request.'})
            return

        if not question:
            self._send(400, {'error': 'Question cannot be empty.'})
            return

        caller = self.headers.get('x-forwarded-for', '').split(',')[0].strip() or 'unknown'
        counter_key = f'{participant_id}:{caller}'
        if question_counts.get(counter_key, 0) >= MAX_QUESTIONS:
            self._send(429, {'error': 'This participant has reached the five-question limit.'})
            return

        try:
            answer = answer_question(question)
        except Exception as error:
            print(f'Explanation API error: {type(error).__name__}: {error}')
            traceback.print_exc()
            self._send(500, {'error': 'The explanation service could not answer right now.'})
            return

        question_counts[counter_key] = question_counts.get(counter_key, 0) + 1
        self._send(200, {'answer': answer, 'question': question})
