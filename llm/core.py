# llm/core.py

import json
import os
from typing import Any, Dict

import httpx
from dotenv import load_dotenv

# --- Langfuse Integration ---
# Importing get_client and observe in the same manner as your working main.py
from langfuse import get_client, observe

from llm.prompts import REPLY_CLASSIFICATION_PROMPT, SYSTEM_PERSONA

load_dotenv()

# --- Configuration ---
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
LLM_MODEL = "qwen/qwen3-next-80b-a3b-thinking"


@observe()
async def generate_llm_response(
    prompt: str,
    system_message: str,
    temperature: float = 0.5,
) -> Dict[str, Any]:
    """
    Calls the OpenRouter API to get a response from the specified language model.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return {"error": "OPENROUTER_API_KEY not found in environment variables."}

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            # The @observe decorator will automatically trace this function call
            response = await client.post(
                OPENROUTER_API_URL, headers=headers, json=payload
            )
            response.raise_for_status()

            content = response.json()["choices"][0]["message"]["content"]
            return json.loads(content)

        except httpx.HTTPStatusError as e:
            error_msg = f"LLM API request failed with status {e.response.status_code}: {e.response.text}"
            print(error_msg)
            return {"error": error_msg}
        except (json.JSONDecodeError, KeyError) as e:
            error_msg = f"Failed to parse LLM response as JSON: {e}. Raw response: {response.text}"
            print(error_msg)
            return {"error": error_msg, "raw_response": response.text}
        except Exception as e:
            error_msg = f"An unexpected error occurred during LLM call: {e}"
            print(error_msg)
            return {"error": error_msg}


if __name__ == "__main__":
    # --- Example Usage ---

    # Initializes the Langfuse client to be used for trace updates
    langfuse_client = get_client()

    async def test_classify_reply():
        print("\n--- Testing Reply Classification ---")

        test_prompt = REPLY_CLASSIFICATION_PROMPT.format(
            our_last_email_body="Hey, noticed you were hiring. Thought we could help. Open to a call?",
            prospect_reply_body="This sounds interesting. What's the typical cost for a project like this?",
        )

        # Use the client instance to update the current trace, not langfuse_context
        langfuse_client.update_current_span(
            name="test-llm-core-classify",
            tags=["testing", "llm-core"],
        )

        result = await generate_llm_response(
            prompt=test_prompt, system_message=SYSTEM_PERSONA
        )

        print("\nLLM Classification Result:")
        print(json.dumps(result, indent=2))

        assert "intent" in result, "Test Failed: 'intent' key not in response."
        print("\nTest Passed!")

    import asyncio

    asyncio.run(test_classify_reply())
