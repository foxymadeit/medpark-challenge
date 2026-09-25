"""Local ASR + LLM slice of the Medpark minutes pipeline.

Importing this package pins the model libraries to offline mode before they load.
"""

from .offline import enforce_offline

enforce_offline()

__version__ = "0.1.0"
