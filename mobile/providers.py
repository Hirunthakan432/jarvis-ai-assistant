"""Use Jarvis's existing tool loops with Android's TLS transport.

No SDK with native wheels is required in the APK. Provider credentials are read
from Android Keystore-backed storage by the native transport, never Python env.
"""
import json
from types import SimpleNamespace

from integrations.providers import (MAX_CALLS, MAX_ROUNDS, call_tool, check_cancel,
                                    openai_loop, anthropic_loop)


class Block(SimpleNamespace):
    def model_dump(self, **kwargs):
        return vars(self)


class MobileProvider:
    def __init__(self, bridge, provider, model):
        self.bridge, self.provider, self.model = bridge, provider, model

    def request(self, payload):
        response = json.loads(str(self.bridge.request(self.provider, self.model, json.dumps(payload))))
        if not response.get('ok'):
            raise RuntimeError('Provider request unavailable.')
        return response['result']

    def complete(self, messages, registry, on_delta=None, cancel=None, on_event=None):
        check_cancel(cancel)
        # Streaming is deliberately disabled at this adapter boundary; tool validation,
        # loop limits, cancellation between rounds and redaction remain shared.
        if self.provider == 'openai':
            def create(**payload):
                check_cancel(cancel)
                data = self.request(payload)['choices'][0]['message']
                calls = [SimpleNamespace(id=c['id'], function=SimpleNamespace(**c['function']))
                         for c in data.get('tool_calls', [])]
                return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
                    content=data.get('content'), tool_calls=calls))])
            client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
            result = openai_loop(client, self.model, messages, registry, None, cancel, on_event)
        elif self.provider == 'anthropic':
            def create(**payload):
                check_cancel(cancel)
                return SimpleNamespace(content=[Block(**b) for b in self.request(payload)['content']])
            result = anthropic_loop(SimpleNamespace(messages=SimpleNamespace(create=create)),
                                    self.model, messages, registry, None, cancel, on_event)
        elif self.provider == 'gemini':
            result = self._gemini(messages, registry, cancel, on_event)
        else:
            raise ValueError('Unsupported mobile cloud provider.')
        check_cancel(cancel)
        if on_delta:
            on_delta(result)
        return result

    def _gemini(self, messages, registry, cancel, on_event):
        contents = [{'role': 'model' if m['role'] == 'assistant' else 'user',
                     'parts': [{'text': m['content']}]} for m in messages[1:]]
        payload = {'systemInstruction': {'parts': [{'text': messages[0]['content']}]},
                   'contents': contents}
        schemas = registry.schemas()
        if schemas:
            payload['tools'] = [{'functionDeclarations': [
                {'name': s['name'], 'description': s['description'],
                 'parameters': s['parameters']} for s in schemas]}]
        count = 0
        for _ in range(MAX_ROUNDS):
            check_cancel(cancel)
            data = self.request(payload)
            content = data['candidates'][0]['content']
            calls = [p['functionCall'] for p in content.get('parts', []) if 'functionCall' in p]
            if not calls:
                return ''.join(p.get('text', '') for p in content.get('parts', []) if not p.get('thought'))
            count += len(calls)
            if count > MAX_CALLS:
                raise ValueError('Tool limit reached.')
            contents.append(content)  # Preserve thought signatures, just like the SDK adapter.
            contents.append({'role': 'user', 'parts': [{'functionResponse': {
                'name': c['name'], 'response': json.loads(call_tool(registry,
                    c['name'], c.get('args', {}), on_event, cancel))}} for c in calls]})
        raise ValueError('Tool round limit reached.')

    def describe_image(self, data, question):
        raise ValueError('Image attachments are not supported by the mobile interface yet.')
