import json
import os
import re
import time

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage


GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


def get_llm(temperature: float = 0.1) -> ChatGroq:
    if not GROQ_API_KEY:
        raise EnvironmentError(
            "GROQ_API_KEY not set. Get a free key at https://console.groq.com "
            "then run: export GROQ_API_KEY=your_key_here"
        )
    return ChatGroq(
        model=GROQ_MODEL,
        api_key=GROQ_API_KEY,
        temperature=temperature,
    )


def extract_json(text: str) -> dict | list | None:
    """
    Try a few strategies to pull JSON out of LLM output.
    Models sometimes wrap it in markdown fences, sometimes not.
    """
    # strategy 1: direct parse
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # strategy 2: pull out ```json ... ``` block
    match = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # strategy 3: find the first { ... } block
    match = re.search(r"\{[\s\S]+\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def call_llm(system_prompt: str, user_prompt: str, agent_name: str,
             retries: int = 2) -> dict:
    """
    Call Ollama with a system + user prompt. Expects JSON back.
    Returns parsed dict or a fallback error dict on failure.
    """
    llm = get_llm()
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ]

    print(f"  [LLM] {agent_name} → calling {GROQ_MODEL} via Groq...")

    for attempt in range(retries + 1):
        try:
            start = time.time()
            response = llm.invoke(messages)
            elapsed = round(time.time() - start, 2)
            raw = response.content
            print(f"  [LLM] {agent_name} ← response received ({elapsed}s)")

            parsed = extract_json(raw)
            if parsed:
                return parsed

            print(f"  [LLM] {agent_name} — JSON parse failed, attempt {attempt + 1}")
            if attempt < retries:
                messages.append(response)
                messages.append(HumanMessage(
                    content="Your response wasn't valid JSON. Please return only a valid JSON object, "
                            "no markdown, no explanation."
                ))

        except Exception as e:
            print(f"  [LLM] {agent_name} — error: {e}")
            if attempt == retries:
                return {"error": str(e), "agent": agent_name}
            time.sleep(1)

    return {"error": "Failed to get valid JSON after retries", "agent": agent_name, "raw": raw}
