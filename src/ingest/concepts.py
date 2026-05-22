"""Concept extraction from content — hashtags and key terms."""

import re


def extract_concepts(content: str) -> list[str]:
    """Extract concepts from content.

    Returns deduplicated list of:
    - Hashtags like #concept-name
    - CamelCase / PascalCase identifiers
    """
    concepts = set()

    # Hashtags: #concept-name or #ConceptName
    for m in re.finditer(r"#([A-Za-z][A-Za-z0-9_-]+)", content):
        concepts.add(m.group(1).lower().replace("-", " ").replace("_", " "))

    # PascalCase / CamelCase identifiers (at least 2 words joined)
    for m in re.finditer(r"\b([A-Z][a-z]+[A-Z][A-Za-z0-9]+)\b", content):
        concepts.add(m.group(1))

    return sorted(concepts)
