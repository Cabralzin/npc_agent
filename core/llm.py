import os
import json
import time
import logging
import asyncio
from typing import Any, List, Dict, Optional, Union, TypeVar
import aiohttp
import certifi
import ssl
from dotenv import load_dotenv

# Import LangChain message types
try:
    from langchain_core.messages import (
        BaseMessage,
        HumanMessage,
        AIMessage,
        SystemMessage,
        FunctionMessage,
        ToolMessage,
        ChatMessage
    )
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

T = TypeVar('T', bound=BaseMessage)

# Set up logging
logger = logging.getLogger(__name__)

# Create a custom SSL context that skips verification
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# Load .env early so os.getenv can see values
load_dotenv()

# Configure the default certifi CA bundle
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
os.environ['SSL_CERT_FILE'] = certifi.where()

class LLMHarness:
    def __init__(self, model: str = "gpt-3.5-turbo", temperature: float = 0.7, max_retries: int = 3, timeout: int = 45):
        self.model = model
        self.temperature = temperature
        self.max_retries = max_retries
        self.timeout = timeout
        # 1) env/.env
        api_key = os.getenv("OPENAI_API_KEY")
        # 2) streamlit secrets (if available)
        if not api_key:
            try:
                import streamlit as st  # type: ignore
                api_key = st.secrets.get("OPENAI_API_KEY", None)  # type: ignore
            except Exception:
                api_key = None
        self.api_key = api_key
        self.base_url = "https://api.openai.com/v1"
        self._connector = None  # deprecated: avoid persisting connectors across loops
        
        # Configure the session headers
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    @property
    def connector(self):
        # Deprecated; kept for backward compatibility but unused in run().
        # Returns a fresh connector bound to the current loop.
        return aiohttp.TCPConnector(
            ssl=ssl_context,
            limit=100,
            force_close=True,
            enable_cleanup_closed=True,
        )

    def _convert_message_to_dict(self, message: Any) -> Dict[str, Any]:
        """Convert a LangChain message object to a dictionary."""
        if isinstance(message, dict):
            return message
            
        if not LANGCHAIN_AVAILABLE or not isinstance(message, BaseMessage):
            # If it's not a LangChain message, try to convert to string
            return {"role": "user", "content": str(message)}
            
        # Handle LangChain message types
        if isinstance(message, HumanMessage):
            return {"role": "user", "content": message.content}
        elif isinstance(message, AIMessage):
            return {"role": "assistant", "content": message.content}
        elif isinstance(message, SystemMessage):
            return {"role": "system", "content": message.content}
        elif isinstance(message, FunctionMessage):
            return {"role": "function", "name": message.name, "content": message.content}
        elif hasattr(message, 'role') and hasattr(message, 'content'):
            # Generic message with role and content
            return {"role": message.role, "content": message.content}
        else:
            # Fallback for other message types
            return {"role": "user", "content": str(message.content) if hasattr(message, 'content') else str(message)}

    async def run(self, messages: Any) -> str:
        last_error = None
        # Fail fast with clear message if API key is missing
        if not self.api_key:
            raise Exception("OPENAI_API_KEY ausente. Defina no ambiente/.env ou em Streamlit secrets.")
        
        # Convert single message to list if needed
        if not isinstance(messages, (list, tuple)):
            messages = [messages]
            
        # Convert all messages to the expected format
        try:
            formatted_messages = [self._convert_message_to_dict(msg) for msg in messages]
            logger.debug(f"Formatted messages: {json.dumps(formatted_messages, indent=2, ensure_ascii=False)}")
        except Exception as e:
            error_msg = f"Failed to format messages: {str(e)}"
            logger.error(error_msg)
            logger.exception(e)
            raise Exception(error_msg) from e
        
        for attempt in range(self.max_retries):
            try:
                # Prepare the request data
                data = {
                    "model": self.model,
                    "messages": formatted_messages,
                    "temperature": self.temperature,
                    "max_tokens": 1000
                }
                
                logger.debug(f"Sending request to OpenAI API: {json.dumps(data, indent=2, ensure_ascii=False)}")
                
                # Make the API request using a fresh connector per call (safer for Streamlit)
                timeout = aiohttp.ClientTimeout(total=self.timeout)
                async with aiohttp.ClientSession(
                    connector=aiohttp.TCPConnector(
                        ssl=ssl_context,
                        limit=100,
                        force_close=True,
                        enable_cleanup_closed=True,
                    ),
                    headers=self.headers,
                    timeout=timeout,
                ) as session:
                    async with session.post(
                        f"{self.base_url}/chat/completions",
                        json=data,
                        ssl=ssl_context
                    ) as response:
                        # Get the response text for debugging
                        response_text = await response.text()
                        logger.debug(f"Raw API response: {response_text}")
                        
                        # Check for errors
                        try:
                            response.raise_for_status()
                            
                            # Parse the response
                            try:
                                result = json.loads(response_text)
                                logger.debug(f"Parsed API response: {json.dumps(result, indent=2, ensure_ascii=False)}")
                                
                                # Extract the content from the response
                                if "choices" in result and len(result["choices"]) > 0:
                                    content = result["choices"][0]["message"]["content"]
                                    logger.debug(f"Extracted content: {content}")
                                    return content
                                else:
                                    raise Exception("No choices in API response")
                                    
                            except json.JSONDecodeError as e:
                                error_msg = f"Failed to parse API response: {e}"
                                logger.error(f"{error_msg}. Response: {response_text}")
                                raise Exception(error_msg) from e
                                
                        except aiohttp.ClientResponseError as e:
                            logger.error(f"API request failed with status {e.status}: {e.message}")
                            logger.error(f"Response headers: {e.headers}")
                            logger.error(f"Response body: {response_text}")
                            raise
                
            except Exception as e:
                last_error = e
                logger.error(f"Attempt {attempt + 1} failed: {str(e)}", exc_info=True)
                
                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    wait_time = (2 ** attempt) * 0.5
                    logger.info(f"Retrying in {wait_time:.1f} seconds...")
                    await asyncio.sleep(wait_time)
                
        # If we've exhausted all retries, raise the last error
        error_msg = f"Failed after {self.max_retries} attempts. Last error: {str(last_error)}"
        logger.error(error_msg)
        raise Exception(error_msg)
    
    def __del__(self):
        # Avoid async cleanup here; connectors/sessions are per-call and closed by context managers
        pass