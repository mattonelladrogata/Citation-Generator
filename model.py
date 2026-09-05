"""
Model — the CFF fields that actually matter for a piece of research
software, built directly against the real 1.2.0 JSON schema shipped
inside the official `cffconvert` package (copied alongside this file
as `cff_schema_1_2_0.json`, not retyped by hand — a 459-entry license
enum is exactly the kind of list a human transcribes wrong).
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List

_SCHEMA_PATH = Path(__file__).parent / "cff_schema_1_2_0.json"


def load_schema() -> dict:
    with open(_SCHEMA_PATH) as f:
        return json.load(f)


def valid_licenses() -> set:
    return set(load_schema()["definitions"]["license-enum"]["enum"])


_ORCID_RE = re.compile(r"^https://orcid\.org/\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")


@dataclass
class Person:
    family_names: str
    given_names: str
    email: Optional[str] = None
    orcid: Optional[str] = None
    affiliation: Optional[str] = None

    def validate(self) -> List[str]:
        errors = []
        if not self.family_names.strip():
            errors.append("Person.family_names cannot be empty")
        if not self.given_names.strip():
            errors.append("Person.given_names cannot be empty")
        if self.orcid and not _ORCID_RE.match(self.orcid):
            errors.append(
                f"orcid '{self.orcid}' doesn't match the required form "
                f"'https://orcid.org/XXXX-XXXX-XXXX-XXXX'"
            )
        return errors

    def to_cff_dict(self) -> dict:
        d = {"family-names": self.family_names, "given-names": self.given_names}
        if self.email:
            d["email"] = self.email
        if self.orcid:
            d["orcid"] = self.orcid
        if self.affiliation:
            d["affiliation"] = self.affiliation
        return d


@dataclass
class CitationMetadata:
    title: str
    authors: List[Person]
    version: Optional[str] = None
    date_released: Optional[str] = None  # "YYYY-MM-DD"
    license: Optional[str] = None  # must be a real SPDX id from valid_licenses()
    repository_code: Optional[str] = None
    url: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    message: str = "If you use this software, please cite it using the metadata from this file."
    work_type: str = "software"  # "software" or "dataset", per the real schema enum

    def validate(self) -> List[str]:
        """
        Returns a list of problems (empty = clean) BEFORE ever touching
        the real validator — catches the common, easy-to-explain
        mistakes with a message a human can act on immediately, rather
        than a raw jsonschema traceback.
        """
        errors = []
        if not self.title.strip():
            errors.append("title cannot be empty")
        if not self.authors:
            errors.append("at least one author is required")
        for i, author in enumerate(self.authors):
            errors += [f"authors[{i}]: {e}" for e in author.validate()]
        if self.work_type not in ("software", "dataset"):
            errors.append(f"type must be 'software' or 'dataset', got '{self.work_type}'")
        if self.date_released and not re.match(r"^\d{4}-\d{2}-\d{2}$", self.date_released):
            errors.append(f"date_released '{self.date_released}' must be in YYYY-MM-DD form")
        if self.license and self.license not in valid_licenses():
            errors.append(
                f"license '{self.license}' is not a recognized SPDX identifier "
                f"in the CFF schema's own license list"
            )
        return errors
