"""LLM client for reconcile — conflict analysis and content synthesis via Ollama."""

import logging

import httpx

log = logging.getLogger("synapse.llm")

CONFLICT_PROMPT = """Analyze these two knowledge documents and determine if they conflict.

Document A:
Title: {title_a}
Content: {content_a}

Document B:
Title: {title_b}
Content: {content_b}

Respond in this exact JSON format:
{{
  "is_conflict": true/false,
  "conflict_type": "contradiction|overlap|outdated|none",
  "reason": "brief explanation of the conflict or why no conflict exists",
  "supersede_id": "a_or_b_or_none",
  "merged_content": "if conflict, provide merged/resolved content. if no conflict, empty string"
}}

Be conservative: only mark as conflict if the documents genuinely contradict each other.
Overlapping information is not a conflict unless one document contradicts the other."""


async def analyze_conflict(
    doc_a: dict,
    doc_b: dict,
    settings,
    model: str = "qwen3:8b",
) -> dict | None:
    """Use LLM to analyze whether two documents conflict.

    Returns dict with: is_conflict, conflict_type, reason, supersede_id, merged_content
    Returns None if LLM is unavailable.
    """
    import json

    prompt = CONFLICT_PROMPT.format(
        title_a=doc_a.get("title", ""),
        content_a=doc_a.get("content", "")[:2000],
        title_b=doc_b.get("title", ""),
        content_b=doc_b.get("content", "")[:2000],
    )

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{settings.ollama_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                },
            )

            if response.status_code != 200:
                log.warning("LLM request failed: %s", response.status_code)
                return None

            data = response.json()
            text = data.get("response", "").strip()

            # Try to parse JSON from the response
            # LLM may wrap JSON in markdown code blocks
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            result = json.loads(text)

            # Normalize boolean
            if isinstance(result.get("is_conflict"), str):
                result["is_conflict"] = result["is_conflict"].lower() in ("true", "yes")

            return result

    except json.JSONDecodeError as e:
        log.warning("Failed to parse LLM response as JSON: %s", e)
        return None
    except Exception as e:
        log.warning("LLM conflict analysis failed: %s", e)
        return None


async def summarize_content(
    content: str,
    title: str,
    settings,
    model: str = "qwen3:8b",
) -> str | None:
    """Use LLM to summarize content. Returns summary or None."""
    prompt = (
        f"Summarize the following document concisely, preserving key information. "
        f"Keep the summary under 500 words.\n\n"
        f"Title: {title}\n\n"
        f"Content:\n{content[:8000]}"
    )

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{settings.ollama_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                },
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("response", "").strip()
    except Exception as e:
        log.warning("LLM summarization failed: %s", e)

    return None