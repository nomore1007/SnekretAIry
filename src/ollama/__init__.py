"""
Ollama integration module for the personal assistant.

Provides remote LLM communication with security, validation, and error handling.
"""

from .client import OllamaClient, OllamaError

__all__ = ['OllamaClient', 'OllamaError']