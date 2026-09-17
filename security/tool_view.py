"""The model sees only validated capabilities, not approval/admin methods."""
from intelligence.intents import Intent
from security.secrets import redact


class ModelToolView:
    def __init__(self, registry, source, *, allow_internet=True, voice_guard=None, document_budget=6000):
        self._registry, self.source = registry, source
        self.allow_internet, self.voice_guard = allow_internet, voice_guard
        self.document_budget = document_budget
        self.events = 0

    def schemas(self):
        return [schema for schema in self._registry.schemas()
                if self._registry.capabilities.actions[schema['name']].ai_invocable
                and (self.allow_internet or schema['name'] != 'web_search')
                and not (self.source == 'cloud_llm' and schema['name'] == 'read_document')]

    def execute(self, name, arguments):
        try:
            if name not in {s['name'] for s in self.schemas()}:
                raise ValueError('This tool is unavailable in the selected mode. Search for relevant document passages instead of paging cloud documents.')
            intent = self._registry.capabilities.normalize(Intent(name, arguments, source=self.source))
            if self.voice_guard and self._registry.capabilities.actions[name].confirmation_required and self.voice_guard.duplicate(intent):
                return {'status': 'error', 'error': 'Duplicate voice action ignored. Review the existing preview.'}
            if name in {'search_documents', 'read_document'} and self.document_budget <= 0:
                raise ValueError('Document passage budget reached. Narrow the question for more context.')
            self.events += 1
            result = self._registry.execute_intent(intent)
            if result.get('status') == 'ok' and name in {'search_documents', 'read_document'}:
                rows = result['result'] if name == 'search_documents' else [result['result']]
                selected = []
                for row in rows:
                    if self.document_budget <= 0:
                        break
                    row = dict(row)
                    row['text'] = redact(row['text'])[:min(self.document_budget, 1800)]
                    self.document_budget -= len(row['text'])
                    if 'next_offset' in row:
                        row['next_offset'] = None
                    selected.append(row)
                result = {**result, 'result': selected if name == 'search_documents' else selected[0]}
            return result
        except (ValueError, TypeError) as error:
            return {'status': 'error', 'error': str(error) if isinstance(error, ValueError) else 'Invalid tool arguments.'}
