"""
Registry checker for PyPI and GitHub.

Checks whether a package name already exists on PyPI or has
matching repositories on GitHub, so the user can be warned
before scaffolding a conflicting project name.
"""

from dataclasses import dataclass

import httpx

_TIMEOUT = 10


@dataclass
class RegistryMatch:
    """A match found on a package registry or code host."""

    source: str
    name: str
    url: str
    description: str = ""


def check_pypi(name: str) -> RegistryMatch | None:
    """Check if *name* exists as a PyPI package.

    Returns a ``RegistryMatch`` when the package exists, ``None`` when it
    does not (404), or ``None`` on any network/timeout error.
    """
    url = f"https://pypi.org/pypi/{name}/json"
    try:
        response = httpx.get(url, follow_redirects=True, timeout=_TIMEOUT)
    except httpx.HTTPError:
        return None

    if response.status_code != 200:
        return None

    data = response.json()
    info = data.get("info", {})
    return RegistryMatch(
        source="PyPI",
        name=info.get("name", name),
        url=info.get("project_url", f"https://pypi.org/project/{name}/"),
        description=info.get("summary", ""),
    )


_FLET_PACKAGES_URL = "https://github.com/flet-dev/flet/tree/main/sdk/python/packages/{name}"
_FLET_PACKAGES_API = (
    "https://api.github.com/repos/flet-dev/flet/contents/sdk/python/packages/{name}"
)


def check_flet_packages(name: str) -> RegistryMatch | None:
    """Check if *name* exists as an official Flet extension package.

    Queries the ``flet-dev/flet`` monorepo at
    ``sdk/python/packages/<name>``.  Returns a ``RegistryMatch`` when
    the directory exists, ``None`` otherwise (including network errors).
    """
    api_url = _FLET_PACKAGES_API.format(name=name)
    try:
        response = httpx.get(api_url, follow_redirects=True, timeout=_TIMEOUT)
    except httpx.HTTPError:
        return None

    if response.status_code != 200:
        return None

    return RegistryMatch(
        source="Flet SDK",
        name=name,
        url=_FLET_PACKAGES_URL.format(name=name),
        description="Official Flet extension in flet-dev/flet monorepo",
    )


def check_github(query: str, max_results: int = 3) -> list[RegistryMatch]:
    """Search GitHub repositories matching *query*.

    Returns up to *max_results* matches, or an empty list on any
    network/timeout error.
    """
    url = "https://api.github.com/search/repositories"
    params = {"q": query, "per_page": max_results}
    try:
        response = httpx.get(url, params=params, follow_redirects=True, timeout=_TIMEOUT)
    except httpx.HTTPError:
        return []

    if response.status_code != 200:
        return []

    data = response.json()
    results: list[RegistryMatch] = []
    for item in data.get("items", [])[:max_results]:
        results.append(
            RegistryMatch(
                source="GitHub",
                name=item.get("full_name", ""),
                url=item.get("html_url", ""),
                description=item.get("description", "") or "",
            )
        )
    return results
