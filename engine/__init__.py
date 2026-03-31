try:
    from .voice import VoiceGuidance
except Exception:
    VoiceGuidance = None  # type: ignore

from .dataset import DatasetManager
from .markers import MarkerManager, MarkerNames, TRIGGER_CODES
