"""
Comprehensive coverage tests for Service (non-visual) packages.

Downloads the 10 most popular Flutter service packages from pub.dev,
runs the full parse → analyze pipeline, and measures how much of the
Dart package API was successfully mapped to Python/Flet code.

Coverage dimensions:
  1. Method coverage  — Dart class methods mapped to Python async methods
  2. Enum coverage    — Dart enums (including re-exported) mapped to Python enums
  3. Event coverage   — Stream getters mapped to event handlers
  4. Data class coverage — re-exported types resolved to stub dataclasses

These tests require network access on first run; subsequent runs use
the cache at ~/.cache/flet-pkg/.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from flet_pkg.core.analyzer import PackageAnalyzer
from flet_pkg.core.downloader import PubDevDownloader
from flet_pkg.core.models import DartPackageAPI, GenerationPlan
from flet_pkg.core.parser import parse_dart_package_api

# -- Top 10 Flutter Service packages -----------------------------------------

SERVICE_PACKAGES = [
    {
        "flutter_package": "shared_preferences",
        "control_name": "SharedPreferences",
        "description": "Persistent key-value storage",
    },
    {
        "flutter_package": "path_provider",
        "control_name": "PathProvider",
        "description": "File system path provider",
    },
    {
        "flutter_package": "connectivity_plus",
        "control_name": "Connectivity",
        "description": "Network connectivity detection",
    },
    {
        "flutter_package": "device_info_plus",
        "control_name": "DeviceInfo",
        "description": "Device hardware and OS information",
    },
    {
        "flutter_package": "package_info_plus",
        "control_name": "PackageInfo",
        "description": "App package metadata",
    },
    {
        "flutter_package": "permission_handler",
        "control_name": "PermissionHandler",
        "description": "Runtime permission management",
    },
    {
        "flutter_package": "geolocator",
        "control_name": "Geolocator",
        "description": "GPS and location services",
    },
    {
        "flutter_package": "local_auth",
        "control_name": "LocalAuth",
        "description": "Biometric and local authentication",
    },
    {
        "flutter_package": "image_picker",
        "control_name": "ImagePicker",
        "description": "Camera and gallery image selection",
    },
    {
        "flutter_package": "file_picker",
        "control_name": "FilePicker",
        "description": "Cross-platform file selection",
    },
]

MIN_COVERAGE_PCT = 70.0


# -- Coverage report dataclass -----------------------------------------------


@dataclass
class ServiceCoverageReport:
    """Full coverage metrics for a single Flutter service package."""

    flutter_package: str
    control_name: str

    # Source API counts (after filtering internal/mock methods)
    total_dart_methods: int = 0
    total_dart_stream_getters: int = 0
    total_dart_enums: int = 0
    total_dart_helpers: int = 0
    total_reexported_types: int = 0

    # Generated plan counts
    generated_methods: int = 0
    generated_sub_module_methods: int = 0
    generated_events: int = 0
    generated_enums: int = 0
    generated_stubs: int = 0
    generated_sub_modules: int = 0

    @property
    def total_generated_methods(self) -> int:
        return self.generated_methods + self.generated_sub_module_methods

    @property
    def total_source_api(self) -> int:
        """Total source API items (methods + stream getters)."""
        return self.total_dart_methods + self.total_dart_stream_getters

    @property
    def total_generated_api(self) -> int:
        """Total generated API items (methods + events from streams)."""
        return self.total_generated_methods + self.generated_events

    @property
    def method_coverage(self) -> float:
        """Dart API items mapped to Python (methods + stream→events)."""
        if self.total_source_api == 0:
            return 100.0
        return self.total_generated_api / self.total_source_api * 100

    @property
    def enum_coverage(self) -> float:
        """Dart enums (including re-exported) mapped to Python enums/stubs."""
        total = self.total_dart_enums + self.total_reexported_types
        if total == 0:
            return 100.0
        generated = self.generated_enums + self.generated_stubs
        return generated / total * 100

    @property
    def overall_feature_coverage(self) -> float:
        """Weighted overall: methods 70%, enums+types 30%."""
        return self.method_coverage * 0.7 + self.enum_coverage * 0.3

    def summary(self) -> str:
        lines = [
            f"  Package: {self.flutter_package}",
            f"  Control: {self.control_name}",
            "",
            f"  API items: {self.total_generated_api}/{self.total_source_api}"
            f" ({self.method_coverage:.0f}%)",
            f"    -> methods:    {self.total_generated_methods}/{self.total_dart_methods}",
            f"    -> events:     {self.generated_events}/{self.total_dart_stream_getters}",
            f"    -> sub-modules: {self.generated_sub_modules}",
            f"  Enums:   {self.generated_enums}/{self.total_dart_enums}",
            f"  Stubs:   {self.generated_stubs}/{self.total_reexported_types}",
            f"  Helpers: {self.total_dart_helpers}",
            "",
            f"  OVERALL: {self.overall_feature_coverage:.1f}%",
        ]
        return "\n".join(lines)


# -- Helpers ------------------------------------------------------------------


# Internal/mock methods excluded from coverage (not real user API)
_INTERNAL_METHOD_NAMES = {"setMockInitialValues", "setMockMethodCallHandler"}


def _build_service_report(
    flutter_package: str,
    control_name: str,
    api: DartPackageAPI,
    plan: GenerationPlan,
) -> ServiceCoverageReport:
    """Build a coverage report for a service package."""
    report = ServiceCoverageReport(
        flutter_package=flutter_package,
        control_name=control_name,
    )

    # Source API — separate regular methods from stream getters
    for cls in api.classes:
        for m in cls.methods:
            if m.name in _INTERNAL_METHOD_NAMES:
                continue
            if m.is_getter and m.return_type.startswith("Stream"):
                report.total_dart_stream_getters += 1
            else:
                report.total_dart_methods += 1
    # Include top-level functions as methods (path_provider uses these)
    report.total_dart_methods += len(api.top_level_functions)
    report.total_dart_enums = len(api.enums)
    report.total_dart_helpers = len(api.helper_classes)
    report.total_reexported_types = len(api.reexported_types)

    # Plan
    report.generated_methods = len(plan.main_methods)
    report.generated_sub_module_methods = sum(len(s.methods) for s in plan.sub_modules)
    report.generated_events = len(plan.events)
    report.generated_enums = len(plan.enums)
    report.generated_stubs = len(plan.stub_data_classes)
    report.generated_sub_modules = len(plan.sub_modules)

    return report


# -- Fixtures -----------------------------------------------------------------


@pytest.fixture(scope="module")
def downloader():
    return PubDevDownloader()


@pytest.fixture(scope="module")
def analyzer():
    return PackageAnalyzer()


# -- Tests --------------------------------------------------------------------


@pytest.mark.network
@pytest.mark.parametrize(
    "pkg",
    SERVICE_PACKAGES,
    ids=[p["flutter_package"] for p in SERVICE_PACKAGES],
)
class TestServiceCoverage:
    def _run_analysis(self, pkg, downloader, analyzer):
        """Download, parse, and analyze a Flutter service package."""
        flutter_package = pkg["flutter_package"]
        control_name = pkg["control_name"]
        package_name = f"flet_{flutter_package.removesuffix('_plus')}"

        package_path = downloader.download(flutter_package)
        api = parse_dart_package_api(package_path)
        plan = analyzer.analyze(
            api,
            control_name=control_name,
            extension_type="service",
            flutter_package=flutter_package,
            package_name=package_name,
            description=pkg["description"],
        )
        return api, plan

    def test_method_coverage(self, pkg, downloader, analyzer):
        """Method coverage: Dart methods mapped to Python async methods."""
        api, plan = self._run_analysis(pkg, downloader, analyzer)
        report = _build_service_report(pkg["flutter_package"], pkg["control_name"], api, plan)

        print(f"\n{'=' * 60}")
        print(report.summary())
        print(f"{'=' * 60}")

        assert report.method_coverage >= MIN_COVERAGE_PCT, (
            f"{pkg['flutter_package']}: method coverage "
            f"{report.method_coverage:.1f}% < {MIN_COVERAGE_PCT}%"
        )

    def test_produces_output(self, pkg, downloader, analyzer):
        """Pipeline must produce at least some methods or events."""
        api, plan = self._run_analysis(pkg, downloader, analyzer)

        total = (
            len(plan.main_methods)
            + sum(len(s.methods) for s in plan.sub_modules)
            + len(plan.events)
            + len(plan.enums)
        )
        assert total > 0, f"{pkg['flutter_package']}: nothing generated"

    def test_overall_coverage(self, pkg, downloader, analyzer):
        """Weighted overall coverage must be >= 70%."""
        api, plan = self._run_analysis(pkg, downloader, analyzer)
        report = _build_service_report(pkg["flutter_package"], pkg["control_name"], api, plan)

        assert report.overall_feature_coverage >= MIN_COVERAGE_PCT, (
            f"{pkg['flutter_package']}: overall coverage "
            f"{report.overall_feature_coverage:.1f}% < {MIN_COVERAGE_PCT}%"
        )

    def test_enum_coverage(self, pkg, downloader, analyzer):
        """Direct Dart enums should be mapped.

        Note: re-exported types from platform_interface packages are only
        fully resolved when the pipeline runs resolve_platform_types().
        This test checks parse+analyze coverage, so we only assert on
        direct enums. Re-exported type resolution is logged but not asserted.
        """
        api, plan = self._run_analysis(pkg, downloader, analyzer)
        report = _build_service_report(pkg["flutter_package"], pkg["control_name"], api, plan)

        # Direct enums (from the package itself)
        if report.total_dart_enums == 0 and report.total_reexported_types == 0:
            pytest.skip("No enums or re-exported types in this package")

        if report.total_dart_enums > 0:
            direct_pct = report.generated_enums / report.total_dart_enums * 100
            assert direct_pct >= MIN_COVERAGE_PCT, (
                f"{pkg['flutter_package']}: direct enum coverage "
                f"{direct_pct:.1f}% < {MIN_COVERAGE_PCT}% "
                f"({report.generated_enums}/{report.total_dart_enums})"
            )

        # Log re-exported type resolution (informational, not asserted)
        if report.total_reexported_types > 0:
            resolved = report.generated_enums + report.generated_stubs
            print(
                f"  Re-exported types: {resolved}/{report.total_reexported_types} "
                f"resolved (full pipeline needed for complete resolution)"
            )
