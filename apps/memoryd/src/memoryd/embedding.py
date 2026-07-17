from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass


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
