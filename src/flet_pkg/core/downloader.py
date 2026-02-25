"""
Pub.dev package downloader.

Downloads Flutter package source tarballs from pub.dev with
local caching to avoid repeated downloads.
"""

from __future__ import annotations

import tarfile
from dataclasses import dataclass
from pathlib import Path

import httpx

from flet_pkg.ui.console import console


class PackageNotFoundError(Exception):
    """Raised when a package is not found on pub.dev."""


class DownloadError(Exception):
    """Raised when a download fails."""


@dataclass
class PackageMetadata:
    """Metadata for a pub.dev package."""

    name: str
    version: str
    description: str = ""
    homepage: str = ""
    repository: str = ""


class PubDevDownloader:
    """Downloads and caches Flutter packages from pub.dev.

    Packages are cached in ``~/.cache/flet-pkg/{name}-{version}/``
    so repeated runs are instantaneous.
    """

    PUB_API = "https://pub.dev/api/packages/{name}"
    TARBALL_URL = "https://pub.dev/packages/{name}/versions/{version}.tar.gz"
    CACHE_DIR = Path.home() / ".cache" / "flet-pkg"

    def __init__(self, cache_dir: Path | None = None):
        self.cache_dir = cache_dir or self.CACHE_DIR

    def fetch_metadata(self, package_name: str) -> PackageMetadata:
        """Fetch package metadata from pub.dev.

        Args:
            package_name: The pub.dev package name.

        Returns:
            PackageMetadata with name, version, description, etc.

        Raises:
            PackageNotFoundError: If the package doesn't exist.
            DownloadError: On network errors.
        """
        url = self.PUB_API.format(name=package_name)
        try:
            response = httpx.get(url, follow_redirects=True, timeout=30)
        except httpx.HTTPError as e:
            raise DownloadError(f"Failed to fetch metadata for '{package_name}': {e}") from e

        if response.status_code == 404:
            raise PackageNotFoundError(f"Package '{package_name}' not found on pub.dev.")
        if response.status_code != 200:
            raise DownloadError(
                f"Unexpected status {response.status_code} fetching '{package_name}'."
            )

        data = response.json()
        latest = data.get("latest", {}).get("pubspec", {})
        return PackageMetadata(
            name=package_name,
            version=data.get("latest", {}).get("version", ""),
            description=latest.get("description", ""),
            homepage=latest.get("homepage", ""),
            repository=latest.get("repository", ""),
        )

    def download(self, package_name: str, version: str | None = None) -> Path:
        """Download a Flutter package source tarball from pub.dev.

        Args:
            package_name: The pub.dev package name.
            version: Specific version to download. If None, uses latest.

        Returns:
            Path to the extracted package directory.

        Raises:
            PackageNotFoundError: If the package doesn't exist.
            DownloadError: On network/extraction errors.
        """
        if version is None:
            metadata = self.fetch_metadata(package_name)
            version = metadata.version

        cache_path = self.cache_dir / f"{package_name}-{version}"
        if cache_path.exists() and (cache_path / "lib").exists():
            return cache_path

        url = self.TARBALL_URL.format(name=package_name, version=version)
        with console.status(f"[info]Downloading {package_name} v{version}...[/info]"):
            try:
                response = httpx.get(url, follow_redirects=True, timeout=60)
            except httpx.HTTPError as e:
                raise DownloadError(f"Failed to download '{package_name}': {e}") from e

            if response.status_code == 404:
                raise PackageNotFoundError(
                    f"Package '{package_name}' version '{version}' not found."
                )
            if response.status_code != 200:
                raise DownloadError(
                    f"Unexpected status {response.status_code} downloading '{package_name}'."
                )

            cache_path.mkdir(parents=True, exist_ok=True)
            tarball_path = cache_path / "package.tar.gz"
            tarball_path.write_bytes(response.content)

            try:
                with tarfile.open(tarball_path, "r:gz") as tar:
                    tar.extractall(cache_path, filter="data")
            except tarfile.TarError as e:
                raise DownloadError(f"Failed to extract '{package_name}': {e}") from e
            finally:
                tarball_path.unlink(missing_ok=True)

        return cache_path
