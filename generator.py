"""
Generator + validator. The generator turns a CitationMetadata object
into real CFF YAML. The validator doesn't reimplement the schema check
— it shells out to the actual `cffconvert --validate` CLI, the same
tool a human or a CI pipeline would run. If our YAML is wrong, we find
out from the same authority a real user would, not from our own
possibly-mistaken idea of what's valid.
"""

import subprocess
import tempfile
from pathlib import Path
from typing import Tuple, Optional

import yaml

from .model import CitationMetadata


def generate_cff_dict(meta: CitationMetadata) -> dict:
    doc = {
        "cff-version": "1.2.0",
        "message": meta.message,
        "title": meta.title,
        "type": meta.work_type,
        "authors": [a.to_cff_dict() for a in meta.authors],
    }
    if meta.version:
        doc["version"] = meta.version
    if meta.date_released:
        doc["date-released"] = meta.date_released
    if meta.license:
        doc["license"] = meta.license
    if meta.repository_code:
        doc["repository-code"] = meta.repository_code
    if meta.url:
        doc["url"] = meta.url
    if meta.keywords:
        doc["keywords"] = meta.keywords
    return doc


def generate_cff_yaml(meta: CitationMetadata) -> str:
    doc = generate_cff_dict(meta)
    # sort_keys=False preserves a sensible, conventional field order
    # (cff-version/message/title first) instead of alphabetizing it
    # into something harder for a human to skim
    return yaml.dump(doc, sort_keys=False, allow_unicode=True, default_flow_style=False)


def validate_cff_yaml(yaml_text: str) -> Tuple[bool, Optional[str]]:
    """
    Writes the YAML to a temp file and runs the REAL `cffconvert
    --validate` CLI against it. Returns (is_valid, error_message).
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".cff", delete=False) as f:
        f.write(yaml_text)
        temp_path = f.name
    try:
        result = subprocess.run(
            ["cffconvert", "--validate", "-i", temp_path],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            return True, None
        return False, (result.stderr or result.stdout).strip()
    finally:
        Path(temp_path).unlink(missing_ok=True)


def generate_and_validate(meta: CitationMetadata) -> Tuple[str, bool, Optional[str]]:
    """
    The full pipeline: pre-flight checks (model.validate — fast, clear
    messages) are the caller's job before this; this function always
    also runs the REAL external validator regardless, since a
    pre-flight check passing is not proof the actual schema accepts
    it — only the real tool's verdict is.
    """
    yaml_text = generate_cff_yaml(meta)
    is_valid, error = validate_cff_yaml(yaml_text)
    return yaml_text, is_valid, error
