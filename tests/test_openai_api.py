"""OpenAI integration regressions without live credentials or paid requests."""
import unittest
from dataclasses import replace
from unittest.mock import Mock, patch
from config import SETTINGS
from providers import OpenAIProvider, create_provider


class OpenAIAPITests(unittest.TestCase):
    def test_missing_key_does_not_construct_cloud_provider(self):
        settings = replace(SETTINGS, llm_provider='openai', openai_api_key=None)
        self.assertIsNone(create_provider(settings))

    def test_sdk_configuration_and_provider_selection(self):
        with patch('openai.OpenAI') as sdk:
            provider = OpenAIProvider('test-only-not-a-real-key', 'test-model')
            self.assertEqual(provider.provider, 'openai')
            self.assertEqual(provider.model, 'test-model')
            sdk.assert_called_once_with(api_key='test-only-not-a-real-key',
                                        timeout=60.0, max_retries=1)

    def test_cloud_provider_uses_existing_adapter(self):
        with patch('openai.OpenAI'):
            settings = replace(SETTINGS, llm_provider='openai',
                               openai_api_key='test-only-not-a-real-key',
                               model='test-model')
            provider = create_provider(settings)
            self.assertIsInstance(provider, OpenAIProvider)
            self.assertEqual(provider.model, 'test-model')


if __name__ == '__main__':
    unittest.main()
