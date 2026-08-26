# llm.py — UPDATED
#
# WHAT CHANGED AND WHY:
# Gemini free tier caps generation at 20 requests/DAY — far too restrictive
# for active development (a single query_understanding.py test run burns
# half that budget). Groq's free tier is 14,400 requests/day, genuinely
# postpay if exceeded (no prepay lump sum), and has NO embedding endpoint —
# so it only ever replaces call_llm(), never touches embeddings.
#
# call_llm() is now a DISPATCHER — it reads config.LLM_PROVIDER and routes
# to Gemini or Groq underneath. Every file that already calls call_llm()
# (query_understanding.py, generate.py) needs ZERO changes.

import json
import time
from google import genai
from google.genai import types
from groq import Groq
import config

_gemini_client = None
_groq_client = None


def get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _gemini_client


def get_groq_client():
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=config.GROQ_API_KEY)
    return _groq_client


def call_llm(system: str, user: str, temperature: float = 0.0, response_schema=None) -> str:
    """
    Single entry point every file should call. Routes to whichever
    provider is set in config.LLM_PROVIDER — "gemini" or "groq".
    """
    if config.LLM_PROVIDER == "groq":
        return _call_llm_groq(system, user, temperature, response_schema)
    else:
        return _call_llm_gemini(system, user, temperature, response_schema)


def _call_llm_gemini(system: str, user: str, temperature: float, response_schema=None) -> str:
    client = get_gemini_client()
    config_kwargs = {"system_instruction": system, "temperature": temperature}
    if response_schema is not None:
        config_kwargs["response_mime_type"] = "application/json"
        config_kwargs["response_schema"] = response_schema

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=user,
                config=types.GenerateContentConfig(**config_kwargs),
            )
            return response.text
        except Exception as e:
            if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
                wait = 15 * (attempt + 1)
                print(f"[Gemini] Rate limited — waiting {wait}s (attempt {attempt + 1}/3)...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("[Gemini] Failed after 3 retries — still rate limited.")


def _call_llm_groq(system: str, user: str, temperature: float, response_schema=None) -> str:
    """
    ⚠️ ONE REAL DIFFERENCE FROM GEMINI, worth knowing:
    Gemini's response_schema FORCES valid, schema-matching JSON at the
    decoding level. Groq's JSON mode only guarantees syntactically valid
    JSON — it does NOT guarantee the fields match your Pydantic schema.
    We compensate by writing the schema into the prompt as instructions,
    which works well in practice but is not a hard guarantee the way
    Gemini's is. query_understanding.py has a retry-on-validation-failure
    to handle the rare case this produces a mismatched shape.
    """
    client = get_groq_client()
    effective_system = system
    kwargs = {"temperature": temperature, "max_tokens": 2048}

    if response_schema is not None:
        schema_json = json.dumps(response_schema.model_json_schema(), indent=2)
        effective_system += (
            f"\n\nRespond with ONLY valid JSON matching this exact schema. "
            f"No markdown, no code fences, no explanation — JSON only:\n{schema_json}"
        )
        kwargs["response_format"] = {"type": "json_object"}

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {"role": "system", "content": effective_system},
                    {"role": "user", "content": user},
                ],
                **kwargs,
            )
            return response.choices[0].message.content
        except Exception as e:
            if "rate_limit" in str(e).lower() or "429" in str(e):
                wait = 15 * (attempt + 1)
                print(f"[Groq] Rate limited — waiting {wait}s (attempt {attempt + 1}/3)...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("[Groq] Failed after 3 retries — still rate limited.")