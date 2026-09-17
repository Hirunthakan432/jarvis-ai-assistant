"""Exercise the real CLI with all AI/voice imports and socket connections denied."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class OfflineArchitectureTests(unittest.TestCase):
    def test_full_local_workflow_without_ai_sdk_model_or_network(self):
        code='''
import importlib.abc
import socket
import sys
class RejectModels(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'openai','anthropic','google','sentence_transformers','torch','vosk','speech_recognition'}:
            raise AssertionError('Local mode attempted a model/SDK import: '+fullname)
sys.meta_path.insert(0,RejectModels())
def no_network(*args,**kwargs):raise AssertionError('Unexpected socket connection')
socket.socket.connect=no_network
sys.argv=['main.py','--text','--mode','LOCAL_ONLY']
from main import main
main()
'''
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            note=root/'notes.txt';note.write_text('Plants make food using sunlight. Photosynthesis produces oxygen.')
            commands=['/diagnostics','/memory create study_preferences style=visual',
                '/attach '+str(note),'/docsearch solar nutrition','/control on','make display half bright',
                '/cancel','/learn quiet time => /media mute','quiet time','/stop','Explain physics','exit']
            env=dict(os.environ,JARVIS_CONFIG_PATH=str(root/'missing.env'),JARVIS_MEMORY_PATH=str(root/'memory.db'),
                     DEFAULT_LLM='openai',OPENAI_API_KEY='unused',JARVIS_AI_ENABLED='true')
            result=subprocess.run([sys.executable,'-c',code],input='\n'.join(commands)+'\n',
                capture_output=True,text=True,timeout=20,cwd=Path(__file__).resolve().parents[1],env=env)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('"database": "ok"',result.stdout)
        self.assertIn('local_vector',result.stdout)
        self.assertIn('"percent": 50',result.stdout)
        self.assertIn('Learned locally',result.stdout)
        self.assertIn('No model was called',result.stdout)
        self.assertNotIn('[CLOUD AI]',result.stdout)


if __name__=='__main__':unittest.main()
