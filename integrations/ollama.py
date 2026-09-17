"""Native local Ollama chat, streaming and capability discovery; no AI SDK."""
import ipaddress
import json
import time
from urllib.parse import urlsplit, urlunsplit

from integrations.providers import MAX_CALLS, MAX_ROUNDS, call_tool, check_cancel


def local_endpoint(url):
    parsed = urlsplit(url)
    if parsed.scheme not in {'http', 'https'} or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Ollama endpoint must be HTTP(S), without credentials, query or fragment.')
    try:
        parsed.port
    except ValueError as error:
        raise ValueError('Invalid Ollama endpoint port.') from error
    if parsed.hostname != 'localhost':
        try:
            address = ipaddress.ip_address(parsed.hostname or '')
        except ValueError as error:
            raise ValueError('Ollama must use localhost or a literal private/loopback IP.') from error
        networks = [ipaddress.ip_network(n) for n in ('127.0.0.0/8', '::1/128', '10.0.0.0/8',
                    '172.16.0.0/12', '192.168.0.0/16', 'fc00::/7')]
        if not any(address in network for network in networks):
            raise ValueError('Ollama must use a private or loopback address.')
    path = parsed.path.rstrip('/')
    if path.endswith('/v1'):
        path = path[:-3]
    if path not in {'', '/api'}:
        raise ValueError('Use an Ollama server root, /api or legacy /v1 URL.')
    return urlunsplit((parsed.scheme, parsed.netloc, '', '', ''))


class OllamaProvider:
    provider = 'ollama'

    def __init__(self, endpoint, model, timeout=60):
        self.endpoint, self.model, self.timeout = local_endpoint(endpoint), model, timeout
        if not isinstance(model, str) or not model.strip() or len(model) > 200:
            raise ValueError('Configure a local Ollama model name.')
        if model.casefold().endswith((':cloud', '-cloud')):
            raise ValueError('Hosted Ollama models cannot be used as LOCAL AI. Select a downloaded local model.')
        self._capabilities = None
        self._checked_at = 0

    def _request(self, path, payload, *, stream=False, cancel=None):
        import requests
        check_cancel(cancel)
        start = time.monotonic()
        with requests.Session() as session:
            session.trust_env = False
            with session.post(self.endpoint + path, json=payload, stream=True,
                    allow_redirects=False, timeout=(3, min(10, self.timeout))) as response:
                if response.status_code != 200:
                    raise ValueError('Ollama unavailable or model not installed. Local commands still work.')
                size = 0
                data = bytearray()
                for chunk in response.iter_content(chunk_size=1024):
                    check_cancel(cancel)
                    if time.monotonic() - start > self.timeout:
                        raise ValueError('Ollama request timed out.')
                    size += len(chunk)
                    if size > 4 * 1024 * 1024:
                        raise ValueError('Ollama response exceeded its size limit.')
                    data.extend(chunk)
                    if stream:
                        while b'\n' in data:
                            line, _, rest = data.partition(b'\n')
                            data = bytearray(rest)
                            if line.strip():
                                yield json.loads(line)
                if data.strip():
                    yield json.loads(data)
        check_cancel(cancel)

    def capabilities(self, cancel=None, refresh=False):
        if refresh or self._capabilities is None or time.monotonic() - self._checked_at > 60:
            values = list(self._request('/api/show', {'model': self.model}, cancel=cancel))
            info = values[0] if len(values) == 1 else None
            if not isinstance(info, dict) or info.get('remote_host') or info.get('remote_model'):
                raise ValueError('A downloaded local Ollama model is required for LOCAL AI.')
            available = info.get('capabilities', [])
            if not isinstance(available, list):
                raise ValueError('Invalid Ollama capability response.')
            self._capabilities = {name for name in available if name in {'completion', 'tools', 'vision'}}
            self._checked_at = time.monotonic()
        return set(self._capabilities)

    def probe(self):
        try:
            capabilities = self.capabilities(refresh=True)
            return {'status': 'available', 'capabilities': sorted(capabilities)}
        except Exception:
            return {'status': 'unavailable', 'message': 'Ollama unavailable — continuing in local command mode.'}

    def complete(self, messages, registry=None, on_delta=None, cancel=None, on_event=None):
        capabilities = self.capabilities(cancel)
        schemas = ([{'type': 'function', 'function': s} for s in registry.schemas()]
                   if registry and 'tools' in capabilities else [])
        transcript = list(messages)
        count = 0
        for _ in range(MAX_ROUNDS):
            check_cancel(cancel)
            payload = {'model': self.model, 'messages': transcript, 'stream': bool(on_delta)}
            if schemas:
                payload['tools'] = schemas
            text, calls, finished = '', [], False
            for chunk in self._request('/api/chat', payload, stream=bool(on_delta), cancel=cancel):
                if not isinstance(chunk, dict) or 'error' in chunk:
                    raise ValueError('Ollama could not complete this request.')
                message = chunk.get('message', {})
                part = message.get('content', '')
                if not isinstance(part, str):
                    raise ValueError('Invalid Ollama text response.')
                text += part
                if part and on_delta:
                    on_delta(part)
                calls.extend(message.get('tool_calls') or [])
                if len(calls) + count > MAX_CALLS:
                    raise ValueError('Tool limit reached. Please split the request.')
                finished = finished or chunk.get('done') is True
            if not finished:
                raise ValueError('Ollama stream ended before completion.')
            if not calls:
                return text
            if not schemas:
                raise ValueError('This Ollama model did not advertise tool support. No tools were executed.')
            count += len(calls)
            transcript.append({'role': 'assistant', 'content': text, 'tool_calls': calls})
            for call in calls:
                function = call.get('function', {})
                name = function.get('name')
                if not isinstance(name, str):
                    raise ValueError('Invalid Ollama tool name.')
                result = call_tool(registry, name, function.get('arguments', {}), on_event, cancel)
                transcript.append({'role': 'tool', 'tool_name': name, 'content': result})
        raise ValueError('Tool round limit reached. Please split the request.')

    def describe_image(self, data, question):
        if 'vision' not in self.capabilities():
            raise ValueError('Selected Ollama model does not advertise vision support.')
        parts = self._request('/api/chat', {'model': self.model, 'stream': False,
            'messages': [{'role': 'user', 'content': question, 'images': [data]}]})
        values = list(parts)
        result = values[0] if len(values) == 1 else None
        if not isinstance(result, dict) or not result.get('done'):
            raise ValueError('Ollama could not describe the image.')
        return result.get('message', {}).get('content', '')
