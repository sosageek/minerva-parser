"""Espone il Judge e il controllo di Ollama"""

from .judge import judge
from .client import OllamaError, is_available
from .models import JudgeResult, PROMPT_VERSION
