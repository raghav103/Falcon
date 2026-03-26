"""
Agent loop — the ReAct engine powered by Ollama (local LLM).

Flow:
  1. Build messages: system prompt + chat history + user question
  2. Call Ollama (local LLM with function calling)
  3. If Ollama returns tool calls → execute via shell.py → append results → loop
  4. If Ollama returns text → stream to client as text_delta events → done
  5. Safety: max 15 iterations

This is an async generator. The FastAPI route iterates over it
and converts each yielded dict into an SSE event.

Events yielded:
  {"type": "tool_start", "name": "search_code", "arguments": {...}}
  {"type": "tool_end",   "name": "search_code"}
  {"type": "text_delta", "content": "The auth module..."}
  {"type": "done"}
  {"type": "error",      "content": "..."}
"""

import json
import logging
from typing import AsyncGenerator, Optional, List, Dict, Any

import aiohttp
import asyncpg

from backend.config import OLLAMA_BASE_URL, OLLAMA_MODEL
from backend.exceptions import AgentError
from backend.tools.definitions import SYSTEM_PROMPT, TOOLS
from backend.tools.shell import execute_tool

logger = logging.getLogger("falcon.agent")
MAX_ITERATIONS = 15


async def run_agent(
    conn: asyncpg.Connection,
    repo_id: str,
    question: str,
    history: Optional[List[Dict]] = None,
    model: Optional[str] = None,
) -> AsyncGenerator[Dict, None]:
    """
    Async generator that runs the agentic ReAct loop using Ollama.

    Args:
        conn:      asyncpg connection (for tool execution)
        repo_id:   which repo the tools operate on
        question:  the user's question
        history:   prior messages [{"role": "user"|"assistant", "content": "..."}]
        model:     Ollama model to use (defaults to config)

    Yields:
        dicts with "type" key — see module docstring for event types.
    """
    model = model or OLLAMA_MODEL
    logger.info(f"Starting agent loop with model: {model}")

    # --- Build the initial messages array ---
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": question})

    # --- ReAct loop ---
    for iteration in range(MAX_ITERATIONS):
        logger.debug(f"Agent iteration {iteration + 1}/{MAX_ITERATIONS}")

        try:
            # Call Ollama API (similar to OpenAI format)
            response_data = await _call_ollama(
                model=model,
                messages=messages,
                tools=TOOLS,
            )

            # Debug: Log the full Ollama response
            logger.info(f"Ollama response: {json.dumps(response_data, indent=2)}")

            # Check if response contains tool calls
            if response_data.get("message", {}).get("tool_calls"):
                logger.info(f"Found {len(response_data['message']['tool_calls'])} tool calls")
                async for event in _handle_tool_calls(
                    conn, repo_id, messages, response_data["message"]["tool_calls"]
                ):
                    yield event
                continue

            # Handle text response
            content = response_data.get("message", {}).get("content", "")
            logger.info(f"Got text content: '{content[:100]}{'...' if len(content) > 100 else ''}'")
            if content:
                # Stream text content
                words = content.split()
                for i, word in enumerate(words):
                    word_with_space = word if i == len(words) - 1 else word + " "
                    yield {"type": "text_delta", "content": word_with_space}

                # Add assistant message to conversation
                messages.append({"role": "assistant", "content": content})
                yield {"type": "done"}
                return

        except Exception as e:
            logger.error(f"Agent error on iteration {iteration + 1}: {e}", exc_info=True)
            yield {
                "type": "error",
                "content": f"Error during processing: {str(e)}"
            }
            return

    #--- Safety: hit max iterations ---
    logger.warning(f"Agent reached max iterations ({MAX_ITERATIONS})")
    yield {
        "type": "text_delta",
        "content": (
            "\n\n---\n"
            "I've reached the maximum exploration depth. "
            "Here's my best answer based on what I've found so far."
        ),
    }
    yield {"type": "done"}


async def _call_ollama(
    model: str,
    messages: List[Dict],
    tools: List[Dict],
) -> Dict:
    """
    Call Ollama API with function calling support.

    Ollama uses a similar format to OpenAI for function calling.
    """
    logger.debug(f"Calling Ollama with model: {model}")

    # Prepare request payload
    payload = {
        "model": model,
        "messages": messages,
        "tools": tools,
        "stream": False,  # We'll handle streaming ourselves
        "options": {
            "temperature": 0.1,  # Lower temperature for more focused responses
            "top_p": 0.9,
        }
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise AgentError(
                        f"Ollama API error: {response.status} - {error_text}",
                        user_message="LLM service temporarily unavailable. Please try again."
                    )

                result = await response.json()
                logger.debug("Ollama response received")
                return result

        except aiohttp.ClientError as e:
            raise AgentError(
                f"Failed to connect to Ollama: {e}",
                user_message="Cannot connect to local LLM service. Please ensure Ollama is running."
            )


async def _handle_tool_calls(
    conn: asyncpg.Connection,
    repo_id: str,
    messages: List[Dict],
    tool_calls: List[Dict]
) -> AsyncGenerator[Dict, None]:
    """Handle tool calls from Ollama response."""

    # Add assistant message with tool calls
    messages.append({
        "role": "assistant",
        "tool_calls": tool_calls,
    })

    # Execute each tool call
    for tool_call in tool_calls:
        name = tool_call["function"]["name"]
        arguments_str = tool_call["function"]["arguments"]

        # Parse arguments
        try:
            arguments = json.loads(arguments_str) if isinstance(arguments_str, str) else arguments_str
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse tool arguments: {arguments_str}, error: {e}")
            arguments = {}

        # Notify frontend: tool execution starting
        yield {
            "type": "tool_start",
            "name": name,
            "arguments": arguments,
        }

        try:
            # Execute via shell.py dispatcher
            result = await execute_tool(conn, repo_id, name, arguments)
        except Exception as e:
            logger.error(f"Tool execution failed: {name}, error: {e}")
            result = f"Tool execution failed: {str(e)}"

        # Notify frontend: tool execution done
        yield {"type": "tool_end", "name": name}

        # Append tool result to messages
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.get("id", f"call_{name}"),
            "content": str(result),
        })