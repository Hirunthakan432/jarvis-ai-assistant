"""Small local default; optional neural embeddings load from disk only."""
import hashlib
import math
from pathlib import Path
import re

STOP = set('a an the is are was were be been being and or of to in on at for from with '
           'my your our how what why when where does do can could would should it this that'.split())
CONCEPTS = (
    ('electricity', 'electric', 'electrical', 'current'),
    ('plant', 'plants', 'photosynthesis'),
    ('sunlight', 'sunshine', 'solar'),
    ('food', 'nutrition', 'nutrients'),
    ('car', 'cars', 'automobile', 'vehicle'),
    ('temperature', 'heat', 'hot', 'thermal'),
    ('rain', 'rainfall', 'precipitation'),
    ('computer', 'pc', 'laptop'),
    ('brightness', 'bright', 'luminance'),
    ('sound', 'audio', 'volume'),
    ('speed', 'velocity', 'fast'),
    ('memory', 'ram'),
    ('distance', 'length', 'range'),
)
CANONICAL = {word: group[0] for group in CONCEPTS for word in group}


def unit(vector):
    norm = math.sqrt(sum(v*v for v in vector.values()))
    return {k: v/norm for k, v in vector.items()} if norm else {}


class ConceptEmbedding:
    """Sparse signed feature vectors with a small explicit synonym vocabulary.

    This is a lightweight lexical-semantic baseline, not a pretrained language
    model. Unknown languages still benefit from exact Unicode token matches.
    """
    signature = 'concept-hash-v1:2048'

    def encode(self, texts):
        output = []
        for text in texts:
            vector = {}
            for token in re.findall(r'\w+', text.casefold()):
                if token in STOP:
                    continue
                token = CANONICAL.get(token, token)
                digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
                key = str(int.from_bytes(digest[:4], 'big') % 2048)
                vector[key] = vector.get(key, 0) + (1 if digest[4] & 1 else -1)
            output.append(unit(vector))
        return output


class SentenceEmbedding:
    def __init__(self, path):
        self.path = Path(path).expanduser()
        self.model = None
        self.signature = 'sentence-v1:' + str(self.path.resolve())

    def encode(self, texts):
        if self.model is None:
            if not self.path.is_dir():
                raise ValueError('Local embedding model directory unavailable.')
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(str(self.path), local_files_only=True, trust_remote_code=False, device='cpu')
        values = self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False, batch_size=16)
        return [{str(i): float(v) for i, v in enumerate(row) if v != 0} for row in values]
