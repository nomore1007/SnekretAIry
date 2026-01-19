"""
Email integration module for reading and analyzing emails.

Provides secure email access with LLM-powered analysis for news briefs and todo suggestions.
"""

from .processor import EmailProcessor, EmailConfigError, EmailConnectionError

__all__ = ['EmailProcessor', 'EmailConfigError', 'EmailConnectionError']