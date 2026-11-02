
#!/usr/bin/env python3

import json
import re
import sys
import urllib.request
import urllib.error

from packaging.specifiers import SpecifierSet
from packaging.version import Version

PYPI = "https://pypi.org/pypi"
PYTHON_VERSION = "3.11"

_cache = {}


def fetch_json(url):
    """Fetch JSON data from PyPI."""
    if url in _cache:
        return _cache[url]

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "requirements-checker/1.0"}
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.load(response)

    except urllib.error.HTTPError as error:
        if error.code == 404:
            data = None
        else:
            raise

    _cache[url] = data
    return data


def parse_line(raw):
    """Extract package name and pinned version."""

    line = raw.split("#", 1)[0].strip()

    if not line or line.startswith("-"):
        return None

    match = re.match(
        r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*==\s*([^\s;]+)",
        line
    )

    if not match:
        return None

    return match.group(1), match.group(2)


def get_minimum_python(requires_python):
    """Find the minimum Python version required by a release."""

    if not requires_python:
        return None

    try:
        specifiers = SpecifierSet(requires_python)

        minimum = None
        minimum_operator = None

        for spec in specifiers:
            if spec.operator not in (">=", ">", "==", "~="):
                continue

            version = Version(spec.version)

            if minimum is None or version > minimum:
                minimum = version
                minimum_operator = spec.operator

        if minimum is None:
            return None

        return minimum, minimum_operator

    except Exception:
        return None


def main(path):

    checked = 0
    not_found = []
    incompatible = []
    highest_requirement = None

    with open(path, encoding="utf-8") as file:
        lines = file.readlines()

    for raw in lines:

        parsed = parse_line(raw)

        if parsed is None:
            continue

        name, version = parsed
        checked += 1

        # Check whether the package exists on PyPI
        package_data = fetch_json(f"{PYPI}/{name}/json")

        if package_data is None:
            not_found.append(f"{name}=={version}")
            continue

        # Check whether the pinned release exists
        release_data = fetch_json(
            f"{PYPI}/{name}/{version}/json"
        )

        if release_data is None:
            not_found.append(f"{name}=={version}")
            continue

        # Get Python version requirements
        requires_python = (
            release_data.get("info", {}).get("requires_python")
        )

        if not requires_python:
            continue

        # Check compatibility with Python 3.11
        try:
            compatible = SpecifierSet(
                requires_python
            ).contains(PYTHON_VERSION)

        except Exception:
            continue

        if not compatible:
            incompatible.append(f"{name}=={version}")

        # Find the highest minimum Python requirement
        minimum = get_minimum_python(requires_python)

        if minimum is not None:

            min_version, operator = minimum

            if (
                highest_requirement is None
                or min_version > highest_requirement[0]
            ):
                highest_requirement = (
                    min_version,
                    name,
                    version,
                    operator
                )

    # Print results
    print(f"Dependencies checked: {checked}")

    print(f"Not found on PyPI: {len(not_found)}")

    print(
        f"Incompatible with Python 3.11: "
        f"{len(incompatible)}"
    )

    if highest_requirement:

        min_version, name, version, operator = highest_requirement

        print(
            f"Highest requirement: "
            f"{name}=={version} "
            f"({operator}{min_version})"
        )

    else:
        print("Highest requirement: none")


if __name__ == "__main__":

    requirements_file = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "requirements.txt"
    )

    main(requirements_file)
