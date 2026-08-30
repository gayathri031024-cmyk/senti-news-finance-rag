"""
Local embedding provider.

A dependency-free, deterministic embedding using the "hashing trick"
(feature hashing, as in scikit-learn's HashingVectorizer / Vowpal
Wabbit): stopwords are removed, each remaining token is hashed to a
dimension index and a sign, term frequencies are accumulated, and the
result is L2-normalized.

This is NOT a substitute for a real trained embedding model — it has
no notion of synonyms or semantic similarity beyond literal word
overlap. It exists so the retrieval pipeline (storage, pgvector
indexing, cosine similarity, hybrid combination with keyword search)
can be built, tested, and demonstrated without any external API call
or multi-hundred-MB model download. Financial queries in this
prototype's target domain (e.g. "GNPA", "net interest income") are
themselves fairly keyword-heavy, so word-overlap embeddings aren't as
degenerate a stand-in here as they'd be for more paraphrase-heavy
queries — but for real semantic search quality, use
EMBEDDING_PROVIDER=openai (or another real provider) with a valid
EMBEDDING_API_KEY.
"""
import hashlib
import math
import re

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# A short, standard stopword list. Filtering these out matters more than
# it would for a trained model — with pure word-overlap hashing, common
# words like "the"/"was"/"what" otherwise add noise that can outweigh
# the meaningful, topic-specific tokens a query actually cares about.
_STOPWORDS = frozenset(
    """
    a an the of to in on for and or is was were are be been being
    this that these those it its as at by from with without into
    what which who whom how when where why did does do
    """.split()
)


class LocalHashingEmbeddingProvider:
    def __init__(self, dimensions: int):
        self.dimensions = dimensions

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = [
            t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS
        ]

        for token in tokens:
            digest = hashlib.md5(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
            vector = [v / norm for v in vector]
        return vector

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]
