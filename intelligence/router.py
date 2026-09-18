"""Resolve local commands to normalized intents before considering a model."""
import json
from intelligence.intents import Intent
from intelligence.semantic import semantic_action, control_like
from tools.local_commands import natural_action, strip_address, normalize, looks_like_control


class IntentRouter:
    def __init__(self, local, registry, *, deterministic=True, learned=True, semantic=True):
        self.local, self.registry = local, registry
        self.deterministic, self.learned, self.semantic = deterministic, learned, semantic

    def resolve(self, message):
        text = strip_address(message, self.local.assistant_name)
        error = None
        if self.deterministic:
            try:
                action = natural_action(text, self.registry.apps)
                if action:
                    self.local._validate(action)
                    return self._intent(action, 'deterministic', 1.0)
            except ValueError as exc:
                error = exc
        if self.learned:
            with self.local.store.connect() as db:
                row = db.execute('SELECT action,arguments FROM local_phrases WHERE phrase=?',
                                 (normalize(text),)).fetchone()
            if row:
                from tools.local_commands import LocalAction
                action = LocalAction(row[0], json.loads(row[1]))
                self.local._validate(action)
                return self._intent(action, 'learned', 1.0)
        if self.semantic:
            action = semantic_action(text, self.registry.apps, self.registry.device_manager.aliases())
            if action:
                return self._intent(action, 'semantic', 0.96)
        if error:
            raise error
        if looks_like_control(text) or control_like(text):
            raise ValueError('No exact local command matched. No action was requested and no AI was called. '
                             'Please clarify the target and value. Request one action at a time; type /local for examples.')
        return None

    def _intent(self, action, source, confidence):
        return self.registry.capabilities.normalize(Intent(action.name, action.arguments, confidence, source))
