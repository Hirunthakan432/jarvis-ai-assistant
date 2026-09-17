"""Pure, inspectable routing policy. No implicit switch to a paid provider."""
from dataclasses import dataclass

MODES = {'LOCAL_ONLY', 'LOCAL_AI', 'HYBRID', 'CLOUD_ALLOWED'}


@dataclass(frozen=True)
class FallbackPolicy:
    mode: str
    local_ai: bool
    cloud_fallback: bool
    configured_provider: str

    def levels(self, ai_enabled=True):
        if not ai_enabled or self.mode == 'LOCAL_ONLY':
            return ()
        local = self.local_ai or self.configured_provider == 'ollama'
        if self.mode == 'LOCAL_AI':
            return ('ollama',) if local else ()
        if self.mode == 'HYBRID':
            return (('ollama',) if local else ()) + (('cloud',) if self.cloud_fallback else ())
        # Existing explicitly configured cloud providers keep working. Switching
        # away from a selected Ollama backend still requires cloud_fallback.
        cloud = self.configured_provider != 'ollama' or self.cloud_fallback
        if local:
            return ('ollama',) + (('cloud',) if cloud and self.cloud_fallback else ())
        return ('cloud',) if cloud else ()

    @property
    def allows_internet(self):
        return self.mode in {'HYBRID', 'CLOUD_ALLOWED'}
