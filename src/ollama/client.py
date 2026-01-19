"""
Ollama client for LLM integration.

Handles remote Ollama communication with timeout, error handling, and response validation.
"""

import json
import time
from typing import Dict, List, Optional, Any, Union

import requests

from config import config
from utils import get_logger


logger = get_logger(__name__)


class OllamaError(Exception):
    """Ollama-specific errors."""
    pass


class OllamaClient:
    """Client for communicating with remote Ollama server."""

    def __init__(self, skip_connection_test: bool = False, default_timeout: Optional[int] = None):
        """
        Initialize the Ollama client.

        Args:
            skip_connection_test: Skip connection test on initialization (for testing)
            default_timeout: Default timeout in seconds (uses config if None)
        """
        self.session = requests.Session()
        self.default_timeout = default_timeout or config.ollama_timeout

        # Test connection on initialization (unless skipped)
        if not skip_connection_test:
            self._test_connection()

    def _test_connection(self) -> None:
        """Test connection to Ollama server."""
        try:
            # Use a longer timeout for connection testing since models can be slow to start
            response = self.session.get(f"{config.ollama_url}/api/tags", timeout=self.default_timeout)
            response.raise_for_status()
            logger.info("Successfully connected to Ollama server")
        except requests.RequestException as e:
            raise OllamaError(f"Cannot connect to Ollama server at {config.ollama_url}: {e}")

    def get_available_models(self) -> List[Dict[str, Any]]:
        """
        Get list of available models from Ollama server.

        Returns:
            List of model information dictionaries
        """
        try:
            response = self.session.get(f"{config.ollama_url}/api/tags")
            response.raise_for_status()
            data = response.json()

            models = data.get('models', [])
            logger.info(f"Found {len(models)} available models")
            return models

        except requests.RequestException as e:
            logger.error(f"Failed to get models: {e}")
            raise OllamaError(f"Cannot retrieve models from Ollama: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response: {e}")
            raise OllamaError(f"Invalid response from Ollama server: {e}")

    def detect_model_capabilities(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Detect capabilities of a specific model or the configured default model.

        Args:
            model_name: Name of model to check (uses config default if None)

        Returns:
            Dictionary with model capabilities
        """
        model = model_name or config.ollama_model
        models = self.get_available_models()

        # Find the model
        model_info = None
        for m in models:
            if m.get('name') == model:
                model_info = m
                break

        if not model_info:
            available_names = [m.get('name', 'unknown') for m in models]
            raise OllamaError(f"Model '{model}' not found. Available models: {available_names}")

        # Extract capabilities (Ollama doesn't provide detailed capability info,
        # so we provide basic info and assume text generation capability)
        capabilities = {
            'name': model_info.get('name'),
            'size': model_info.get('size', 0),
            'modified_at': model_info.get('modified_at', ''),
            'supports_text_generation': True,
            'max_context_length': 4096,  # Conservative default, could be detected
            'supported_formats': ['text', 'json']
        }

        logger.info(f"Detected capabilities for model {model}: {capabilities}")
        return capabilities

    def generate_text(
        self,
        prompt: str,
        model: Optional[str] = None,
        stream: bool = False,
        options: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None
    ) -> Union[str, Dict[str, Any]]:
        """
        Generate text using Ollama.

        Args:
            prompt: Input prompt
            model: Model name (uses config default if None)
            stream: Whether to stream the response
            options: Additional model options
            timeout: Request timeout in seconds (uses default if None)

        Returns:
            Generated text or full response dict if streaming
        """
        model_name = model or config.ollama_model

        payload = {
            'model': model_name,
            'prompt': prompt,
            'stream': stream
        }

        if options:
            payload['options'] = options

        try:
            request_timeout = timeout if timeout is not None else self.default_timeout
            logger.debug(f"Sending generate request to Ollama for model {model_name}")
            start_time = time.time()

            response = self.session.post(
                config.ollama_generate_endpoint,
                json=payload,
                timeout=request_timeout
            )

            response.raise_for_status()

            if stream:
                return self._handle_streaming_response(response)
            else:
                return self._handle_single_response(response, start_time)

        except requests.Timeout:
            logger.error(f"Request timed out after {request_timeout} seconds")
            raise OllamaError(f"Ollama request timed out after {request_timeout} seconds")
        except requests.RequestException as e:
            logger.error(f"Ollama request failed: {e}")
            raise OllamaError(f"Ollama request failed: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response from Ollama: {e}")
            raise OllamaError(f"Invalid response format from Ollama: {e}")

    def _handle_single_response(self, response: requests.Response, start_time: float) -> str:
        """
        Handle a single (non-streaming) response from Ollama.

        Args:
            response: HTTP response object
            start_time: Request start time for timing

        Returns:
            Generated text
        """
        data = response.json()

        # Validate response structure
        if 'response' not in data:
            raise OllamaError("Invalid Ollama response: missing 'response' field")

        generated_text = data['response']

        # Log performance metrics
        duration = time.time() - start_time
        eval_count = data.get('eval_count', 0)
        eval_duration = data.get('eval_duration', 0)

        logger.info(
            f"Generated {len(generated_text)} characters in {duration:.2f}s "
            f"(eval_count: {eval_count}, eval_duration: {eval_duration}ns)"
        )

        return generated_text

    def _handle_streaming_response(self, response: requests.Response) -> Dict[str, Any]:
        """
        Handle a streaming response from Ollama.

        Args:
            response: HTTP response object (streaming)

        Returns:
            Dictionary with full response data
        """
        full_response = {
            'response': '',
            'done': False,
            'context': [],
            'total_duration': 0,
            'load_duration': 0,
            'prompt_eval_count': 0,
            'prompt_eval_duration': 0,
            'eval_count': 0,
            'eval_duration': 0
        }

        for line in response.iter_lines():
            if line:
                try:
                    chunk = json.loads(line.decode('utf-8'))

                    # Accumulate response text
                    if 'response' in chunk:
                        full_response['response'] += chunk['response']

                    # Update metadata from final chunk
                    if chunk.get('done', False):
                        full_response.update({
                            'done': True,
                            'context': chunk.get('context', []),
                            'total_duration': chunk.get('total_duration', 0),
                            'load_duration': chunk.get('load_duration', 0),
                            'prompt_eval_count': chunk.get('prompt_eval_count', 0),
                            'prompt_eval_duration': chunk.get('prompt_eval_duration', 0),
                            'eval_count': chunk.get('eval_count', 0),
                            'eval_duration': chunk.get('eval_duration', 0)
                        })

                        logger.info(
                            f"Streaming response completed: {len(full_response['response'])} chars, "
                            f"eval_count: {full_response['eval_count']}"
                        )
                        break

                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse streaming chunk: {e}")
                    continue

        return full_response

    def validate_structured_response(self, response: Union[str, Dict[str, Any]], expected_format: str) -> Dict[str, Any]:
        """
        Validate that a response conforms to an expected structured format.

        Args:
            response: Raw response text or dict
            expected_format: Expected format ('json', 'yaml', etc.)

        Returns:
            Parsed and validated response

        Raises:
            OllamaError: If response format is invalid
        """
        # If response is already a dict, return it for json/yaml formats
        if isinstance(response, dict):
            return response

        if expected_format.lower() == 'json':
            try:
                assert isinstance(response, str)
                parsed = json.loads(response)
                return parsed
            except json.JSONDecodeError as e:
                raise OllamaError(f"Response is not valid JSON: {e}")

        elif expected_format.lower() == 'yaml':
            raise OllamaError("YAML format validation not yet implemented")

        else:
            # For other formats, just return the text
            return {'text': response}

    def generate_with_validation(
        self,
        prompt: str,
        expected_format: str = 'text',
        model: Optional[str] = None,
        max_retries: int = 2,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate text with response validation and retries.

        Args:
            prompt: Input prompt
            expected_format: Expected response format ('text', 'json', 'yaml')
            model: Model name
            max_retries: Maximum number of retries on validation failure
            **kwargs: Additional arguments for generate_text

        Returns:
            Validated response dictionary
        """
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                raw_response = self.generate_text(prompt, model=model, **kwargs)

                # Validate response format
                validated_response = self.validate_structured_response(raw_response, expected_format)

                return {
                    'success': True,
                    'response': validated_response,
                    'raw_response': raw_response,
                    'attempt': attempt + 1
                }

            except (OllamaError, json.JSONDecodeError, ValueError) as e:
                last_error = e
                if attempt < max_retries:
                    logger.warning(f"Response validation failed (attempt {attempt + 1}/{max_retries + 1}): {e}")
                    continue
                else:
                    logger.error(f"Response validation failed after {max_retries + 1} attempts: {e}")

        return {
            'success': False,
            'error': str(last_error),
            'attempts': max_retries + 1
        }