from __future__ import annotations

import hashlib
import math
import os
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class HashingEmbedder:
    dimension: int
    salt: str = 'memorymesh-starter-v1'

    def embed(self, text: str) -> list[float]:
        if self.dimension <= 0:
            raise ValueError('dimension must be positive')
        vector = [0.0] * self.dimension
        tokens = [token for token in self._tokenize(text) if token]
        if not tokens:
            return vector
        for token in tokens:
            digest = hashlib.sha256(f'{self.salt}:{token}'.encode('utf-8')).digest()
            idx = int.from_bytes(digest[:4], 'big') % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[idx] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return [token.strip(".,!?;:()[]{}\n\t\r\"'").lower() for token in text.split()]


@dataclass(frozen=True)
class RemoteEmbedder:
    """Real SEMANTIC embeddings from a SOVEREIGN embedding endpoint (a local Ollama or any OpenAI-compatible
    /v1/embeddings server — no vendor lock, runs on the node). This is what makes 'car' ≈ 'automobile' instead
    of orthogonal, the thing the hashing embedder structurally cannot do. Handles both the OpenAI shape
    ({data:[{embedding}]}) and the Ollama native shape ({embedding} / {embeddings:[...]})."""

    url: str
    model: str
    dimension: int
    api_key: str = ''
    timeout: float = 10.0

    def embed(self, text: str) -> list[float]:
        headers = {'content-type': 'application/json'}
        if self.api_key:
            headers['authorization'] = f'Bearer {self.api_key}'
        r = httpx.post(self.url, json={'model': self.model, 'input': text}, headers=headers, timeout=self.timeout)
        r.raise_for_status()
        vec = _extract_embedding(r.json())
        if not vec:
            raise ValueError('embedding endpoint returned no vector')
        return vec

    def probe(self) -> bool:
        """One startup probe — is the endpoint reachable and returning vectors? Decides embedder selection ONCE
        so the whole store shares one vector space (never mix semantic + hashed vectors, which are incomparable)."""
        try:
            return len(self.embed('probe')) > 0
        except Exception:  # noqa: BLE001
            return False


def _extract_embedding(body: object) -> list[float]:
    if isinstance(body, dict):
        if isinstance(body.get('embedding'), list):                       # Ollama native
            return [float(x) for x in body['embedding']]
        emb = body.get('embeddings')
        if isinstance(emb, list) and emb and isinstance(emb[0], list):    # Ollama batch
            return [float(x) for x in emb[0]]
        data = body.get('data')
        if isinstance(data, list) and data and isinstance(data[0], dict): # OpenAI shape
            return [float(x) for x in data[0].get('embedding', [])]
    return []


def build_embedder(dimension: int, salt: str) -> object:
    """Select the embedder ONCE at startup. If EMBEDDINGS_URL is set AND reachable → real semantic vectors;
    otherwise the deterministic hashing fallback (honest: logs which, so retrieval quality is never a mystery)."""
    url = os.getenv('EMBEDDINGS_URL', '').strip()
    if url:
        remote = RemoteEmbedder(
            url=url,
            model=os.getenv('EMBEDDINGS_MODEL', 'nomic-embed-text'),
            dimension=dimension,
            api_key=os.getenv('EMBEDDINGS_API_KEY', ''),
            timeout=float(os.getenv('EMBEDDINGS_TIMEOUT', '10')),
        )
        if remote.probe():
            print(f'[memoryd] semantic embeddings ACTIVE via {url} ({remote.model})')
            return remote
        print(f'[memoryd] EMBEDDINGS_URL set ({url}) but unreachable — falling back to hashing embedder')
    return HashingEmbedder(dimension=dimension, salt=salt)
