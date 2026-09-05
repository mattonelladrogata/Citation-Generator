# citation-gen

Generates a valid `CITATION.cff` file directly from an existing
`pyproject.toml` — the metadata (name, version, authors, license,
repository) that nearly every Python research project already has,
turned into a real, officially-validated citation file in one command.

## Why this exists

Researchers are told to add a `CITATION.cff` to their software so it
can be cited properly. In practice, almost nobody does — not because
they don't care, but because it means hand-writing YAML for
information the project already declares somewhere else. This removes
that step entirely for the common case.

## What's real about this, not just claimed

- The license enum (**459 entries**) and required-field list used for
  validation are extracted directly from the official CFF 1.2.0 JSON
  schema shipped inside the real `cffconvert` package — not retyped
  by hand, which is exactly how a 459-entry list gets silently wrong.
- Every generated file is checked by actually invoking
  **`cffconvert --validate`**, the same tool a GitHub Action or a human
  reviewer would run — not by our own idea of what the schema allows.
- Tested against two other real `pyproject.toml` files built this
  session — and this is where a real gap was found and fixed: the
  license extractor only handled `license = "MIT"` and
  `license = {text = "MIT"}`, missing the very common
  `license = {file = "LICENSE"}` form entirely. Fixed by falling back
  to the `License :: OSI Approved :: ...` classifier, the same idea
  used in the `sbom-checker` project for the identical underlying
  problem (declared license metadata isn't in one consistent place).

## Install

```bash
pip install -e ".[dev]"
pytest tests/ -v   # 20 tests, validated against the real cffconvert tool
```

## Use

```bash
python -m citation_gen --from-pyproject pyproject.toml -o CITATION.cff
```

```python
from citation_gen.pyproject_extractor import extract_from_pyproject
from citation_gen.generator import generate_and_validate

meta = extract_from_pyproject("pyproject.toml")
yaml_text, is_valid, error = generate_and_validate(meta)
```

## What's not built (honest scope)

- Author name splitting ("Jacopo Antonelli Drago" → family/given) is a
  documented heuristic (last word = family name), not a real name
  parser — it's wrong for names that don't follow that order, and the
  result is meant to be reviewed, not blindly trusted.
- Only PEP 621-style `[project]` tables are supported; legacy
  `setup.py`/`setup.cfg`-only projects aren't parsed.
- Format conversion (CFF → BibTeX, APA, etc.) is something
  `cffconvert` itself already does well — not duplicated here.

## License

MIT — see `LICENSE`.
