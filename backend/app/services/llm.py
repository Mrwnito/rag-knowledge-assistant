from __future__ import annotations

import os
from typing import Literal
import httpx
import json
from typing import AsyncIterator

Provider = Literal["ollama", "openai"]

def get_provider() -> Provider:
    # default local
    return os.getenv("LLM_PROVIDER", "ollama").lower()  # type: ignore[return-value]

def get_ollama_model() -> str:
    return os.getenv("OLLAMA_MODEL", "llama3.2:3b")

def get_openai_model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini")

def get_openai_api_key() -> str | None:
    return os.getenv("OPENAI_API_KEY")

async def generate(provider: Provider, prompt: str) -> tuple[str, str]:
    """
    Returns: (answer, used_model)
    """
    if provider == "ollama":
        model = get_ollama_model()
        # Ollama API: POST http://localhost:11434/api/generate
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                "http://127.0.0.1:11434/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.2,
                        "num_predict": 220
                    }
                },
            )
            r.raise_for_status()
            data = r.json()
            return data.get("response", "").strip(), model

    if provider == "openai":
        key = get_openai_api_key()
        if not key:
            raise RuntimeError("OPENAI_API_KEY is missing")
        model = get_openai_model()
        # OpenAI Chat Completions compatible endpoint style
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant that answers ONLY using the provided context."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                },
            )
            r.raise_for_status()
            data = r.json()
            answer = data["choices"][0]["message"]["content"].strip()
            return answer, model

    raise RuntimeError(f"Unknown provider: {provider}")

async def generate_stream_ollama(prompt: str) -> AsyncIterator[str]:
    model = get_ollama_model()
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream(
            "POST",
            "http://127.0.0.1:11434/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": True,
                "options": {"temperature": 0.2, "num_predict": 260},
            },
        ) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line:
                    continue
                data = json.loads(line)
                chunk = data.get("response", "")
                if chunk:
                    yield chunk
                if data.get("done"):
                    break
