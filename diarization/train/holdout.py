"""Which Common Voice speakers never train, shared by the Kaggle run and the
mixed-language test so both sides pick the same people."""

import hashlib


def held_out(client_id: str) -> bool:
    """Every tenth speaker, by a stable hash of their Common Voice client_id."""
    return int(hashlib.sha1(client_id.encode()).hexdigest(), 16) % 10 == 0
