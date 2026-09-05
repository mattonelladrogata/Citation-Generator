"""
Usage:
    python -m citation_gen --from-pyproject pyproject.toml -o CITATION.cff
    python -m citation_gen --from-pyproject pyproject.toml --dry-run
"""

import argparse
import sys

from .pyproject_extractor import extract_from_pyproject
from .generator import generate_and_validate


def main():
    parser = argparse.ArgumentParser(prog="citation-gen")
    parser.add_argument("--from-pyproject", required=True, metavar="FILE",
                         help="Path to an existing pyproject.toml to extract metadata from")
    parser.add_argument("-o", "--output", default="CITATION.cff",
                         help="Output path (default: CITATION.cff)")
    parser.add_argument("--dry-run", action="store_true",
                         help="Print the generated YAML instead of writing it")
    args = parser.parse_args()

    try:
        meta = extract_from_pyproject(args.from_pyproject)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    pre_flight = meta.validate()
    if pre_flight:
        print("Pre-flight check found issues (fix these for a more complete citation):")
        for issue in pre_flight:
            print(f"  - {issue}")
        print()

    yaml_text, is_valid, error = generate_and_validate(meta)

    if not is_valid:
        print("The generated file did NOT pass the official cffconvert validator:", file=sys.stderr)
        print(error, file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        print(yaml_text)
    else:
        with open(args.output, "w") as f:
            f.write(yaml_text)
        print(f"Wrote a validated CITATION.cff to {args.output}")


if __name__ == "__main__":
    main()
