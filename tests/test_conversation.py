import unittest

from core.conversation import Conversation


class ConversationTests(unittest.TestCase):
    def test_reset_keeps_system_prompt(self):
        conversation = Conversation("System instructions", max_messages=2)
        conversation.add("user", "Hello")
        conversation.reset()
        self.assertEqual(
            conversation.messages,
            [{"role": "system", "content": "System instructions"}],
        )

    def test_context_is_bounded_and_preserves_system_prompt(self):
        conversation = Conversation("System instructions", max_messages=2)
        conversation.add("user", "One")
        conversation.add("assistant", "Two")
        conversation.add("user", "Three")
        self.assertEqual(
            conversation.messages,
            [
                {"role": "system", "content": "System instructions"},
                {"role": "assistant", "content": "Two"},
                {"role": "user", "content": "Three"},
            ],
        )


if __name__ == "__main__":
    unittest.main()
