"""Memory migration, retrieval, local audit privacy and device adapters."""
from dataclasses import replace
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch

from assistant import JarvisAssistant
from audit.log import AuditLog
from config import SETTINGS
from diagnostics import diagnose
from intelligence.intents import Intent
from memory.advanced import AdvancedMemory
from memory.structured import CATEGORIES
from security.tool_view import ModelToolView


class StorageUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.path = self.root/'memory.db'
        self.settings = replace(SETTINGS, memory_path=str(self.path), ai_enabled=False,
            apps_json='{"vscode":["code"]}', devices_json='{"meter":"http://192.168.1.4/readings"}')
        self.bot = JarvisAssistant(settings=self.settings)

    def test_memory_crud_all_categories_and_source(self):
        memory = self.bot.memory.structured
        for category in CATEGORIES:
            with self.subTest(category=category):
                memory.put(category,'language','Tamil',create_only=True)
                first = memory.read(category,'language')[0]
                self.assertEqual(first['source'],'user')
                self.assertIsNotNone(first['created_at'])
                with self.assertRaises(ValueError):
                    memory.put(category,'language','English',create_only=True)
                memory.put(category,'language','English',update_only=True)
                self.assertEqual(memory.read(category,'language')[0]['value'],'English')
                self.assertEqual(memory.read(category,'language')[0]['created_at'],first['created_at'])
                memory.delete(category,'language')
                self.assertEqual(memory.read(category,'language'),[])
                with self.assertRaises(ValueError):
                    memory.put(category,'language','Tamil',update_only=True)

    def test_memory_admin_commands_and_device_aliases(self):
        self.assertIn('saved', self.bot.chat('/memory create study_preferences style=visual'))
        self.assertIn('visual', self.bot.chat('/memory read study_preferences style'))
        self.assertIn('saved', self.bot.chat('/memory update study_preferences style=pictures'))
        self.assertIn('forgotten', self.bot.chat('/memory delete study_preferences style'))
        self.assertIn('saved', self.bot.chat('/memory create device_aliases distance=meter'))
        with patch('tools.registry.read_device', return_value={'readings':{'mm':42}}) as read:
            self.assertIn('42', self.bot.chat('read distance'))
            read.assert_called_once_with('meter', self.bot.tools.devices)
        self.assertNotIn('saved', self.bot.chat('/memory create device_aliases internet=http://example.com'))

    def test_legacy_tables_remain_compatible_and_reconcile_rollback_edits(self):
        # This is the original schema, written using the original INSERT shape.
        with self.bot.store.connect() as db:
            db.execute('INSERT INTO facts VALUES (?,?)',('legacy','English'))
            db.execute('INSERT INTO local_phrases VALUES (?,?,?,?)',('study time','study time','open_app','{"name":"vscode"}'))
        restored = JarvisAssistant(settings=self.settings)
        self.assertEqual(restored.memory.facts()['legacy'],'English')
        self.assertIsNone(restored.memory.structured.read('conversation_facts','legacy')[0]['created_at'])
        self.assertIn('confirmation_required', restored.chat('study time'))
        with restored.store.connect() as db:
            db.execute('UPDATE facts SET value=? WHERE key=?',('Tamil','legacy'))
            self.assertEqual(len(db.execute('PRAGMA table_info(local_phrases)').fetchall()),4)
        self.assertEqual(JarvisAssistant(settings=self.settings).memory.facts()['legacy'],'Tamil')
        with restored.store.connect() as db:
            db.execute('DELETE FROM facts WHERE key=?',('legacy',))
        self.assertNotIn('legacy', JarvisAssistant(settings=self.settings).memory.facts())

    def test_memory_update_transaction_rolls_back_on_database_failure(self):
        self.bot.memory.remember('language','Tamil')
        with self.bot.store.connect() as db:
            db.execute("CREATE TRIGGER fail_update BEFORE UPDATE ON facts BEGIN SELECT RAISE(ABORT,'failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.bot.memory.remember('language','English')
        self.assertEqual(self.bot.memory.facts()['language'],'Tamil')

    def test_taught_commands_have_crud_metadata_and_remain_guarded(self):
        self.bot.chat('/learn study time => /open vscode')
        first = json.loads(self.bot.chat('/learned'))[0]
        self.bot.chat('/relearn study time => /media mute')
        second = json.loads(self.bot.chat('/memory list learned_commands'))[0]
        self.assertEqual(first['created_at'],second['created_at'])
        self.assertEqual(second['action'],'media_control')
        self.assertIn('off', self.bot.chat('study time'))
        self.assertIn('keyboard', self.bot.chat('/relearn study time => /open vscode',source='voice'))
        self.bot.chat('/unlearn study time')
        self.assertEqual(self.bot.chat('/learned'),'[]')

    def test_secret_rejection_redaction_and_legacy_preservation(self):
        for key,value in [('api_key','hidden'),('password','hidden'),('credential','sk-'+'a'*30),
                          ('note','my password is hunter2'),('note','Authorization: Bearer abcd1234')]:
            with self.subTest(key=key,value=value):
                with self.assertRaises(ValueError):
                    self.bot.memory.remember(key,value)
        with self.bot.store.connect() as db:
            db.execute('INSERT INTO facts VALUES (?,?)',('password','old-secret'))
        restored = JarvisAssistant(settings=self.settings)
        self.assertNotIn('old-secret', str(restored.memory.facts()))
        with restored.store.connect() as db:
            self.assertEqual(db.execute('SELECT value FROM facts WHERE key="password"').fetchone()[0],'old-secret')
        self.bot.store.save_turn('password=hello', 'Use /confirm deadbeef', 10)
        self.assertNotIn('hello', str(self.bot.store.history(10)))
        self.assertNotIn('deadbeef', str(self.bot.store.history(10)))
        self.assertNotIn('Learned locally', self.bot.chat('/learn secret time => /type sk-'+'a'*30))

    def test_builtin_semantic_retrieval_and_source_offsets(self):
        self.bot.memory.add_document('biology.txt','Plants make food using sunlight. Photosynthesis produces oxygen.')
        self.bot.memory.add_document('computers.txt','A laptop needs RAM and an SSD.')
        rows = self.bot.memory.search_documents('solar nutrition')
        self.assertEqual(rows[0]['name'],'biology.txt')
        self.assertEqual(rows[0]['retrieval'],'local_vector')
        self.assertEqual(rows[0]['source'],'doc:1@0')
        self.assertEqual(self.bot.memory.index.status()['documents_indexed'],2)
        self.assertEqual(self.bot.memory.keyword_search('solar nutrition'),[])

    def test_local_index_reuses_vectors_and_rebuilds_changed_documents(self):
        self.bot.memory.add_document('notes.txt','Rainfall measurement uses a rain gauge.')
        self.bot.memory.search_documents('rain')
        encoder = self.bot.memory.index.encoder
        original = encoder.encode
        with patch.object(encoder,'encode',wraps=original) as encode:
            self.bot.memory.search_documents('rain')
            self.assertEqual(encode.call_count,1)  # Query only; stored chunks reused.
        with self.bot.store.connect() as db:
            db.execute('UPDATE documents SET text=? WHERE id=1',('Temperature is thermal energy information.',))
        self.assertIn('Temperature',self.bot.memory.search_documents('heat')[0]['text'])
        self.bot.memory.remove_document(1)
        self.assertEqual(self.bot.memory.search_documents('heat'),[])
        self.assertEqual(self.bot.memory.index.status()['chunks'],0)

    def test_index_failure_falls_back_without_destroying_documents(self):
        self.bot.memory.add_document('notes.txt','Current in a circuit.')
        with patch.object(self.bot.memory.index,'search',side_effect=RuntimeError('secret')):
            reply = self.bot.chat('/docsearch circuit')
            self.assertIn('keyword retrieval',reply)
            self.assertNotIn('secret',reply)
        self.assertIn('circuit',self.bot.memory.read_document(1)['text'])

    def test_missing_neural_model_does_not_download(self):
        memory = AdvancedMemory(self.bot.store,embedding_backend='sentence_transformers',embedding_model_path=str(self.root/'missing'))
        memory.add_document('notes.txt','A circuit uses current.')
        with patch.dict('sys.modules', {'sentence_transformers':Mock()}) as modules:
            self.assertEqual(memory.search_documents('circuit')[0]['retrieval'],'keyword')
            modules['sentence_transformers'].SentenceTransformer.assert_not_called()

    def test_cloud_document_context_has_shared_budget_and_cannot_page(self):
        self.bot.memory.add_document('private.txt', 'Photosynthesis uses sunlight. '*1000)
        view = ModelToolView(self.bot.tools,'cloud_llm')
        self.assertEqual(view.execute('read_document',{'id':1})['status'],'error')
        first = view.execute('search_documents',{'query':'sunlight'})
        self.assertLessEqual(sum(len(row['text']) for row in first['result']),6000)
        self.assertEqual(view.execute('search_documents',{'query':'sunlight'})['status'],'error')
        self.assertEqual(len(self.bot.memory.read_document(1)['text']),10000)

    def test_audit_is_metadata_only_with_retention(self):
        self.bot.tools.enable_control()
        result = self.bot.tools.execute_intent(Intent('type_text',{'text':'PRIVATE_DOCUMENT'},source='cloud_llm'))
        self.bot.tools.cancel(result['token'])
        rows = self.bot.tools.audit_log.read()
        self.assertNotIn('PRIVATE_DOCUMENT',str(rows))
        self.assertNotIn(result['token'],str(rows))
        self.assertIn('CLOUD AI',str(rows))
        log = AuditLog(self.bot.store,retention_days=1,max_rows=3)
        with patch('audit.log.time.time',return_value=100):
            log.record('open_app','success',parameters={'text':'PRIVATE','percent':50})
        with patch('audit.log.time.time',return_value=100000):
            for _ in range(5):log.record('general_question','success')
        self.assertEqual(len(log.read()),3)
        self.assertTrue(all(row['at']==100000 for row in log.read()))

    def test_device_manager_exposes_capabilities_without_remote_commands(self):
        device = self.bot.tools.device_manager.device('meter')
        self.assertEqual(device.capabilities,('read',))
        with self.assertRaises(ValueError):device.invoke('shell',{'command':'echo'})
        with self.assertRaises(ValueError):device.invoke('read',{'url':'http://example.com'})
        computer = self.bot.tools.device_manager.device('computer')
        result = computer.invoke('open_app',{'name':'vscode'})
        self.assertEqual(result['status'],'confirmation_required')

    def test_esp32_timeout_and_diagnostics_redaction(self):
        import requests
        with patch('requests.Session') as session:
            session.return_value.__enter__.return_value.get.side_effect = requests.Timeout('Authorization: Bearer SECRET')
            reply = self.bot.chat('/device meter')
            self.assertIn('ESP32 device timed out',reply)
            self.assertNotIn('SECRET',reply)
        with patch('requests.Session') as session:
            report = diagnose(self.bot)
            session.assert_not_called()
        self.assertEqual(report['database'],'ok')
        self.assertNotIn('http://',str(report))
        self.assertEqual(report['microphone'],'not_probed')
        self.assertIn('local_speech', report)


if __name__ == '__main__':unittest.main()
