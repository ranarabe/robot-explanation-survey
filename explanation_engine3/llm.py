"""Step 4: the LLM.

Every backend has the same method, so they can be swapped:
    chat(system: str, user: str, json_mode: bool = False) -> str

    OpenAILLM   OpenAI SDK, Responses API   (needs OPENAI_API_KEY)
    OllamaLLM   local Ollama
"""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class OpenAILLM:
    """OpenAI, using the official SDK and the Responses API.

        pip install --user --break-system-packages openai
        export OPENAI_API_KEY="sk-..."          # the SDK reads it automatically
        export OPENAI_MODEL="gpt-6-astra"       # optional

    system prompt -> `instructions`, user prompt -> `input`,
    the answer is `response.output_text`.
    """

    def __init__(self, model=None, temperature=None, client=None):
        # temperature=None: not sent. Newer models (e.g. gpt-6-astra) reject it.
        self.model = model or os.environ.get('OPENAI_MODEL', 'gpt-6-astra')
        self.temperature = temperature
        if client is None:
            if not os.environ.get('OPENAI_API_KEY'):
                raise RuntimeError('OPENAI_API_KEY is not set. Run: export OPENAI_API_KEY="sk-..."')
            try:
                from openai import OpenAI
            except ImportError:
                raise RuntimeError('The openai package is missing. Run: '
                                   'pip install --user --break-system-packages openai') from None
            client = OpenAI()          # reads OPENAI_API_KEY
        self.client = client

    def chat(self, system: str, user: str, json_mode: bool = False) -> str:
        request = {'model': self.model, 'instructions': system, 'input': user}
        if self.temperature is not None:
            request['temperature'] = self.temperature
        if json_mode:
            request['text'] = {'format': {'type': 'json_object'}}
            # OpenAI requires the word "json" in the input itself for JSON mode.
            if 'json' not in user.lower():
                request['input'] = user + '\n\nReply in JSON.'

        try:
            response = self.client.responses.create(**request)
        except Exception as error:
            # Some models only accept the default temperature: retry once without it.
            if 'temperature' in str(error) and 'temperature' in request:
                del request['temperature']
                response = self.client.responses.create(**request)
            else:
                raise RuntimeError(f'OpenAI error: {error}') from error

        answer = (response.output_text or '').strip()
        if not answer:
            raise RuntimeError('OpenAI returned an empty answer.')
        return answer


class OllamaLLM:
    """Local Ollama server."""

    def __init__(self, model='qwen3:8b', base_url='http://127.0.0.1:11434',
                 temperature=0.0, timeout=180):
        self.model = model
        self.base_url = base_url.rstrip('/')
        self.temperature = temperature
        self.timeout = timeout

    def chat(self, system: str, user: str, json_mode: bool = False) -> str:
        payload = {
            'model': self.model,
            'messages': [{'role': 'system', 'content': system},
                         {'role': 'user', 'content': user}],
            'stream': False,
            'think': False,
            'options': {'temperature': self.temperature},
        }
        if json_mode:
            payload['format'] = 'json'
        request = Request(f'{self.base_url}/api/chat', data=json.dumps(payload).encode(),
                          headers={'Content-Type': 'application/json'}, method='POST')
        try:
            with urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read())
        except HTTPError as error:
            raise RuntimeError(f'Ollama HTTP {error.code}: {error.read().decode()}') from error
        except URLError as error:
            raise RuntimeError('Cannot reach Ollama. Is it running? (ollama serve)') from error
        answer = data.get('message', {}).get('content', '').strip()
        if not answer:
            raise RuntimeError('Ollama returned an empty answer.')
        return answer


def make_llm(backend: str, model: str | None = None):
    """'openai' | 'ollama' | 'none' -> client (or None)."""
    if backend == 'none':
        return None
    if backend == 'openai':
        return OpenAILLM(model=model)
    if backend == 'ollama':
        return OllamaLLM(model=model or 'qwen3:8b')
    raise ValueError(f'Unknown LLM backend: {backend}')


def check_openai():
    """Like the example in the OpenAI docs: send one prompt to test the key.

        ros2 run explanation_engine3 check_openai
    """
    try:
        llm = OpenAILLM()
        print(f'Model: {llm.model}')
        print(llm.chat('You are a helpful assistant. Give clear, concise answers.',
                       'Say in one sentence that the connection works.'))
    except RuntimeError as error:
        raise SystemExit(f'[error] {error}') from None
