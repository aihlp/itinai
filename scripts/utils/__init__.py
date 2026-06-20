"""Common utilities for itinai scripts."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def slugify(value: str, fallback: str = "imported-agent") -> str:
    """Convert a string to a URL-friendly slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug or fallback


def truncate(value: str | None, max_length: int) -> str | None:
    """Truncate a string to max_length, normalizing whitespace."""
    if not value:
        return None
    text = " ".join(str(value).split())
    return text[:max_length]


def load_yaml_manifest(path: Path) -> dict[str, Any]:
    """Load and validate a YAML manifest file."""
    import yaml
    
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a YAML object")
    return data
