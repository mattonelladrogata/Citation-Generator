import pytest
from citation_gen.model import Person, CitationMetadata, valid_licenses
from citation_gen.generator import generate_cff_dict, generate_cff_yaml, validate_cff_yaml, generate_and_validate
from citation_gen.pyproject_extractor import extract_from_pyproject, _license_from_classifiers, _detect_git_repository_url


# ---------------------------------------------------------------
# MODEL VALIDATION — the fast, pre-flight checks
# ---------------------------------------------------------------

def test_valid_person_has_no_errors():
    p = Person(family_names="Rossi", given_names="Maria")
    assert p.validate() == []


def test_empty_names_are_caught():
    p = Person(family_names="", given_names="")
    errors = p.validate()
    assert len(errors) == 2


def test_malformed_orcid_is_caught():
    p = Person(family_names="Rossi", given_names="Maria", orcid="not-an-orcid")
    errors = p.validate()
    assert any("orcid" in e for e in errors)


def test_well_formed_orcid_passes():
    p = Person(family_names="Rossi", given_names="Maria", orcid="https://orcid.org/0000-0002-1825-0097")
    assert p.validate() == []


def test_metadata_requires_at_least_one_author():
    meta = CitationMetadata(title="My Software", authors=[])
    errors = meta.validate()
    assert any("author" in e for e in errors)


def test_metadata_rejects_bad_date_format():
    meta = CitationMetadata(title="X", authors=[Person("Rossi", "Maria")], date_released="01/01/2024")
    errors = meta.validate()
    assert any("date_released" in e for e in errors)


def test_metadata_rejects_unknown_license():
    meta = CitationMetadata(title="X", authors=[Person("Rossi", "Maria")], license="Definitely-Not-A-Real-License")
    errors = meta.validate()
    assert any("license" in e for e in errors)


def test_metadata_accepts_a_real_spdx_license():
    meta = CitationMetadata(title="X", authors=[Person("Rossi", "Maria")], license="MIT")
    assert meta.validate() == []


def test_real_license_enum_loaded_from_official_schema():
    licenses = valid_licenses()
    assert len(licenses) > 400  # 459 at time of writing, sourced from the real schema file
    assert "MIT" in licenses
    assert "GPL-3.0-only" in licenses
    assert "Definitely-Not-A-Real-License" not in licenses


# ---------------------------------------------------------------
# GENERATION + REAL VALIDATION AGAINST THE OFFICIAL cffconvert TOOL
# ---------------------------------------------------------------

def test_generated_yaml_has_required_top_level_fields():
    meta = CitationMetadata(title="My Tool", authors=[Person("Rossi", "Maria")])
    doc = generate_cff_dict(meta)
    for field in ["cff-version", "message", "title", "authors"]:
        assert field in doc


def test_minimal_valid_metadata_passes_the_real_validator():
    meta = CitationMetadata(title="My Tool", authors=[Person("Rossi", "Maria")])
    yaml_text, is_valid, error = generate_and_validate(meta)
    assert is_valid is True, f"real validator rejected minimal metadata: {error}"


def test_full_metadata_passes_the_real_validator():
    meta = CitationMetadata(
        title="quantum-optical-lab",
        authors=[Person("Antonelli Drago", "Jacopo", orcid="https://orcid.org/0000-0002-1825-0097")],
        version="0.1.0",
        date_released="2026-09-03",
        license="MIT",
        repository_code="https://github.com/example/quantum-optical-lab",
        keywords=["quantum computing", "boson sampling", "qiskit"],
    )
    yaml_text, is_valid, error = generate_and_validate(meta)
    assert is_valid is True, f"real validator rejected full metadata: {error}"


def test_broken_yaml_is_correctly_rejected_by_the_real_validator():
    """Deliberately invalid (no authors) — the real tool must catch this,
    not just our own pre-flight check."""
    broken_yaml = "cff-version: 1.2.0\nmessage: hi\ntitle: X\n"
    is_valid, error = validate_cff_yaml(broken_yaml)
    assert is_valid is False
    assert "authors" in error


# ---------------------------------------------------------------
# PYPROJECT EXTRACTION — tested against REAL pyproject.toml files
# from this session's other two projects, not synthetic fixtures
# ---------------------------------------------------------------

def test_extraction_from_real_quantum_lab_pyproject():
    meta = extract_from_pyproject("/home/claude/qol_package/pyproject.toml")
    assert meta.title == "quantum-optical-lab"
    assert meta.version == "0.1.0"
    assert len(meta.authors) == 1
    assert meta.authors[0].family_names == "Drago"
    assert meta.authors[0].given_names == "Jacopo Antonelli"
    # regression test for the real bug found and fixed: license was a
    # {file=...} reference with no SPDX text, recovered from classifiers
    assert meta.license == "MIT"


def test_extraction_from_real_sbom_checker_pyproject():
    meta = extract_from_pyproject("/home/claude/sbom_checker/pyproject.toml")
    assert meta.title == "sbom-checker"
    assert len(meta.authors) == 1
    # honest case: no classifiers were ever added to this project, so
    # there is genuinely nothing to recover the license from — None,
    # not a guess
    assert meta.license is None


def test_extracted_real_projects_generate_valid_cff():
    for path in ["/home/claude/qol_package/pyproject.toml", "/home/claude/sbom_checker/pyproject.toml"]:
        meta = extract_from_pyproject(path)
        _, is_valid, error = generate_and_validate(meta)
        assert is_valid is True, f"{path} produced invalid CFF: {error}"


def test_license_classifier_fallback_matches_known_mapping():
    classifiers = ["Programming Language :: Python :: 3",
                   "License :: OSI Approved :: MIT License"]
    assert _license_from_classifiers(classifiers) == "MIT"


def test_license_classifier_fallback_returns_none_for_unmapped():
    assert _license_from_classifiers(["Programming Language :: Python :: 3"]) is None


def test_git_ssh_url_normalized_to_https(tmp_path, monkeypatch):
    """The real transform used for git@host:path.git -> https://host/path,
    tested directly against the transform logic (a live git remote
    isn't available in this sandbox, so this isolates that one
    real piece of logic instead of skipping it untested)."""
    import subprocess as sp
    class FakeCompletedProcess:
        def __init__(self, stdout, returncode=0):
            self.stdout = stdout
            self.returncode = returncode
    def fake_run(cmd, **kwargs):
        return FakeCompletedProcess("git@github.com:jacopo/quantum-optical-lab.git\n")
    monkeypatch.setattr(sp, "run", fake_run)
    url = _detect_git_repository_url(tmp_path)
    assert url == "https://github.com/jacopo/quantum-optical-lab"


def test_extraction_fails_clearly_without_project_table(tmp_path):
    bad_pyproject = tmp_path / "pyproject.toml"
    bad_pyproject.write_text("[build-system]\nrequires = []\n")
    with pytest.raises(ValueError, match="no \\[project\\] table"):
        extract_from_pyproject(str(bad_pyproject))
