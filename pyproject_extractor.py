"""
pyproject.toml extractor — the actual "mega useful" hook: almost every
Python research project already has a pyproject.toml with name,
version, authors, license, and repository URL. This turns those into
a CitationMetadata object automatically, so generating a citation file
for an existing project takes one command, not a form to fill in from
scratch.

WHY THIS MATTERS FOR THE STATED GOAL: the whole point of a
CITATION.cff is that researchers currently DON'T make one, because
writing YAML by hand for something that already exists as project
metadata feels like pointless duplicate work. Removing that friction
is the actual value proposition — not "can generate CFF" (any text
editor can do that), but "can generate CFF FROM WHAT YOU ALREADY HAVE
in thirty seconds."
"""

import tomllib
import subprocess
from pathlib import Path
from typing import Optional

from .model import CitationMetadata, Person


def _license_from_classifiers(classifiers: list) -> Optional[str]:
    """Maps common 'License :: OSI Approved :: X' classifiers to their
    SPDX id. Small and explicit on purpose — silently guessing wrong
    on an unlisted classifier is worse than returning None and letting
    CitationMetadata.validate() flag the missing license honestly."""
    mapping = {
        "MIT License": "MIT",
        "Apache Software License": "Apache-2.0",
        "BSD License": "BSD-3-Clause",
        "GNU General Public License v3 (GPLv3)": "GPL-3.0-only",
        "GNU General Public License v2 (GPLv2)": "GPL-2.0-only",
        "GNU Lesser General Public License v3 (LGPLv3)": "LGPL-3.0-only",
        "Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0",
        "ISC License (ISCL)": "ISC",
    }
    for c in classifiers:
        tail = c.split("::")[-1].strip()
        if tail in mapping:
            return mapping[tail]
    return None


def _split_author_name(full_name: str) -> Person:
    """
    pyproject.toml authors are a single free-text name
    ("Jacopo Antonelli Drago"), CFF wants family/given separately.
    Heuristic: last word is the family name, the rest is given names —
    documented as a heuristic, not claimed to be perfect (it visibly
    fails on names that don't follow this order, and the caller can
    always override the result).
    """
    parts = full_name.strip().split()
    if len(parts) == 1:
        return Person(family_names=parts[0], given_names="")
    return Person(family_names=parts[-1], given_names=" ".join(parts[:-1]))


def _detect_git_repository_url(project_dir: Path) -> Optional[str]:
    """Best-effort: read the git remote if this is a git repo. Never
    raises — a missing/absent git repo is a normal case, not an error."""
    try:
        result = subprocess.run(
            ["git", "-C", str(project_dir), "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            url = result.stdout.strip()
            # normalize a git@github.com:user/repo.git SSH URL into an
            # https one, since that's what CFF's repository-code
            # (an actual "url" per the schema, not any git ref string) expects
            if url.startswith("git@"):
                host_and_path = url[4:].replace(":", "/", 1)
                url = f"https://{host_and_path}"
            return url[:-4] if url.endswith(".git") else url
    except Exception:
        pass
    return None


def extract_from_pyproject(pyproject_path: str) -> CitationMetadata:
    path = Path(pyproject_path)
    with open(path, "rb") as f:
        data = tomllib.load(f)

    project = data.get("project", {})
    if not project:
        raise ValueError(
            f"{pyproject_path} has no [project] table — nothing to extract. "
            f"(Only PEP 621-style pyproject.toml files are supported.)"
        )

    title = project.get("name", "")
    version = project.get("version")

    authors = []
    for a in project.get("authors", []):
        name = a.get("name", "")
        if name:
            person = _split_author_name(name)
            if a.get("email"):
                person.email = a["email"]
            authors.append(person)

    license_field = project.get("license")
    license_id = None
    if isinstance(license_field, dict) and "text" in license_field:
        license_id = license_field["text"]
    elif isinstance(license_field, str):
        license_id = license_field
    if not license_id:
        # license = { file = "LICENSE" } is common (PEP 639-era metadata)
        # and carries no SPDX id directly — fall back to the classifiers,
        # a controlled vocabulary, same idea used in sbom-checker for
        # exactly the same underlying problem
        license_id = _license_from_classifiers(project.get("classifiers", []))

    repo_url = _detect_git_repository_url(path.parent)
    if not repo_url:
        urls = project.get("urls", {})
        repo_url = urls.get("Repository") or urls.get("Source") or urls.get("Homepage")

    return CitationMetadata(
        title=title,
        authors=authors,
        version=version,
        license=license_id,
        repository_code=repo_url,
        keywords=project.get("keywords", []),
    )
