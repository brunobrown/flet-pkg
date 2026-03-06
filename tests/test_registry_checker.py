from unittest.mock import MagicMock, patch

import httpx

from flet_pkg.core.registry_checker import (
    RegistryMatch,
    check_flet_packages,
    check_github,
    check_pypi,
)


class TestCheckPyPI:
    def test_found(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "info": {
                "name": "flet-onesignal",
                "project_url": "https://pypi.org/project/flet-onesignal/",
                "summary": "Flet OneSignal extension",
            }
        }

        with patch("flet_pkg.core.registry_checker.httpx.get", return_value=mock_response):
            result = check_pypi("flet-onesignal")

        assert result is not None
        assert isinstance(result, RegistryMatch)
        assert result.source == "PyPI"
        assert result.name == "flet-onesignal"
        assert result.url == "https://pypi.org/project/flet-onesignal/"
        assert result.description == "Flet OneSignal extension"

    def test_not_found(self):
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("flet_pkg.core.registry_checker.httpx.get", return_value=mock_response):
            result = check_pypi("nonexistent-pkg-xyz-12345")

        assert result is None

    def test_network_error(self):
        with patch(
            "flet_pkg.core.registry_checker.httpx.get",
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            result = check_pypi("flet-onesignal")

        assert result is None

    def test_timeout(self):
        with patch(
            "flet_pkg.core.registry_checker.httpx.get",
            side_effect=httpx.TimeoutException("timed out"),
        ):
            result = check_pypi("flet-onesignal")

        assert result is None

    def test_server_error(self):
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("flet_pkg.core.registry_checker.httpx.get", return_value=mock_response):
            result = check_pypi("flet-onesignal")

        assert result is None

    def test_fallback_url(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "info": {
                "name": "my-pkg",
                "summary": "",
            }
        }

        with patch("flet_pkg.core.registry_checker.httpx.get", return_value=mock_response):
            result = check_pypi("my-pkg")

        assert result is not None
        assert result.url == "https://pypi.org/project/my-pkg/"


class TestCheckGitHub:
    def test_found(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {
                    "full_name": "user/flet-onesignal",
                    "html_url": "https://github.com/user/flet-onesignal",
                    "description": "Flet OneSignal extension",
                },
                {
                    "full_name": "other/flet-onesignal-fork",
                    "html_url": "https://github.com/other/flet-onesignal-fork",
                    "description": None,
                },
            ]
        }

        with patch("flet_pkg.core.registry_checker.httpx.get", return_value=mock_response):
            results = check_github("flet-onesignal")

        assert len(results) == 2
        assert results[0].source == "GitHub"
        assert results[0].name == "user/flet-onesignal"
        assert results[1].description == ""

    def test_no_results(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"items": []}

        with patch("flet_pkg.core.registry_checker.httpx.get", return_value=mock_response):
            results = check_github("nonexistent-pkg-xyz")

        assert results == []

    def test_network_error(self):
        with patch(
            "flet_pkg.core.registry_checker.httpx.get",
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            results = check_github("flet-onesignal")

        assert results == []

    def test_max_results(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {
                    "full_name": f"user/flet-onesignal-{i}",
                    "html_url": f"https://github.com/user/flet-onesignal-{i}",
                    "description": f"Repo {i}",
                }
                for i in range(10)
            ]
        }

        with patch("flet_pkg.core.registry_checker.httpx.get", return_value=mock_response):
            results = check_github("flet-onesignal", max_results=3)

        assert len(results) == 3

    def test_rate_limited(self):
        mock_response = MagicMock()
        mock_response.status_code = 403

        with patch("flet_pkg.core.registry_checker.httpx.get", return_value=mock_response):
            results = check_github("flet-onesignal")

        assert results == []


class TestCheckFletPackages:
    def test_found(self):
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("flet_pkg.core.registry_checker.httpx.get", return_value=mock_response):
            result = check_flet_packages("flet-rive")

        assert result is not None
        assert result.source == "Flet SDK"
        assert result.name == "flet-rive"
        assert "flet-dev/flet" in result.url
        assert "sdk/python/packages/flet-rive" in result.url

    def test_not_found(self):
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("flet_pkg.core.registry_checker.httpx.get", return_value=mock_response):
            result = check_flet_packages("flet-nonexistent-xyz")

        assert result is None

    def test_network_error(self):
        with patch(
            "flet_pkg.core.registry_checker.httpx.get",
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            result = check_flet_packages("flet-rive")

        assert result is None

    def test_timeout(self):
        with patch(
            "flet_pkg.core.registry_checker.httpx.get",
            side_effect=httpx.TimeoutException("timed out"),
        ):
            result = check_flet_packages("flet-rive")

        assert result is None


class TestRegistryMatch:
    def test_defaults(self):
        m = RegistryMatch(source="PyPI", name="pkg", url="https://example.com")
        assert m.description == ""

    def test_with_description(self):
        m = RegistryMatch(
            source="GitHub",
            name="user/repo",
            url="https://github.com/user/repo",
            description="A cool repo",
        )
        assert m.description == "A cool repo"
