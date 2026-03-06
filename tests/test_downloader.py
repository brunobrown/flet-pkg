from unittest.mock import MagicMock, patch

import pytest

from flet_pkg.core.downloader import (
    DownloadError,
    PackageMetadata,
    PackageNotFoundError,
    PubDevDownloader,
)


@pytest.fixture
def downloader(tmp_path):
    return PubDevDownloader(cache_dir=tmp_path / "cache")


class TestFetchMetadata:
    def test_success(self, downloader):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "latest": {
                "version": "5.2.0",
                "pubspec": {
                    "description": "OneSignal Flutter SDK",
                    "homepage": "https://onesignal.com",
                    "repository": "https://github.com/OneSignal/OneSignal-Flutter-SDK",
                },
            }
        }

        with patch("flet_pkg.core.downloader.httpx.get", return_value=mock_response):
            meta = downloader.fetch_metadata("onesignal_flutter")

        assert isinstance(meta, PackageMetadata)
        assert meta.name == "onesignal_flutter"
        assert meta.version == "5.2.0"
        assert meta.description == "OneSignal Flutter SDK"

    def test_not_found(self, downloader):
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("flet_pkg.core.downloader.httpx.get", return_value=mock_response):
            with pytest.raises(PackageNotFoundError):
                downloader.fetch_metadata("nonexistent_package_xyz")

    def test_server_error(self, downloader):
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("flet_pkg.core.downloader.httpx.get", return_value=mock_response):
            with pytest.raises(DownloadError):
                downloader.fetch_metadata("some_package")


class TestDownload:
    def test_cache_hit(self, downloader, tmp_path):
        cache_path = tmp_path / "cache" / "test_pkg-1.0.0"
        cache_path.mkdir(parents=True)
        (cache_path / "lib").mkdir()
        (cache_path / "lib" / "test.dart").write_text("// cached")

        result = downloader.download("test_pkg", version="1.0.0")
        assert result == cache_path
        assert (result / "lib").exists()

    def test_resolves_latest_version(self, downloader):
        meta_response = MagicMock()
        meta_response.status_code = 200
        meta_response.json.return_value = {
            "latest": {
                "version": "2.0.0",
                "pubspec": {"description": "Test"},
            }
        }

        download_response = MagicMock()
        download_response.status_code = 404

        with patch(
            "flet_pkg.core.downloader.httpx.get", side_effect=[meta_response, download_response]
        ):
            with pytest.raises(PackageNotFoundError):
                downloader.download("test_pkg")
