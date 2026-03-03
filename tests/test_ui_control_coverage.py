"""
Comprehensive coverage tests for UI Control (visual widget) packages.

Downloads the 10 most popular Flutter visual widget packages from pub.dev,
runs the full parse → analyze pipeline, and measures how much of the
Dart package API was successfully mapped to Python/Flet code.

Coverage dimensions:
  1. Widget class coverage — how many widget classes were processed
  2. Property coverage    — constructor params mapped to properties/events
  3. Enum coverage        — Dart enums mapped to Python enums

These tests require network access on first run; subsequent runs use
the cache at ~/.cache/flet-pkg/.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from flet_pkg.core.analyzer import PackageAnalyzer
from flet_pkg.core.downloader import PubDevDownloader
from flet_pkg.core.models import DartClass, DartPackageAPI, GenerationPlan
from flet_pkg.core.parser import parse_dart_package_api

# -- Top 10 Flutter UI Control packages ------------------------------------

UI_CONTROL_PACKAGES = [
    {
        "flutter_package": "flutter_spinkit",
        "control_name": "SpinKit",
        "description": "Loading indicators animated with Flutter",
    },
    {
        "flutter_package": "shimmer",
        "control_name": "Shimmer",
        "description": "Shimmer loading effect widget",
    },
    {
        "flutter_package": "carousel_slider",
        "control_name": "CarouselSlider",
        "description": "Carousel slider widget",
    },
    {
        "flutter_package": "percent_indicator",
        "control_name": "PercentIndicator",
        "description": "Circular and linear percent indicators",
    },
    {
        "flutter_package": "flutter_rating_bar",
        "control_name": "RatingBar",
        "description": "Customizable rating bar widget",
    },
    {
        "flutter_package": "flutter_slidable",
        "control_name": "Slidable",
        "description": "Slidable list item widget",
    },
    {
        "flutter_package": "smooth_page_indicator",
        "control_name": "SmoothPageIndicator",
        "description": "Smooth animated page indicators",
    },
    {
        "flutter_package": "readmore",
        "control_name": "ReadMore",
        "description": "Expandable text widget",
    },
    {
        "flutter_package": "marquee",
        "control_name": "Marquee",
        "description": "Scrolling text marquee widget",
    },
    {
        "flutter_package": "auto_size_text",
        "control_name": "AutoSizeText",
        "description": "Auto-resizing text widget",
    },
]

MIN_COVERAGE_PCT = 70.0

# Params always excluded from coverage counting (framework internals)
_FRAMEWORK_PARAMS = {"key", "child", "children"}


# -- Coverage report dataclass ---------------------------------------------


@dataclass
class CoverageReport:
    """Full coverage metrics for a single Flutter package."""

    flutter_package: str
    main_widget: str

    # Widget classes
    total_widget_classes: int = 0
    processed_widget_classes: int = 0  # main + sub-controls

    # Constructor params (across ALL widget classes in the package)
    total_params_all_widgets: int = 0
    # Constructor params (main widget only)
    total_params_main: int = 0
    generated_properties: int = 0
    generated_events: int = 0
    sub_control_features: int = 0

    # Enums
    total_dart_enums: int = 0
    generated_enums: int = 0

    # Data classes
    total_helper_classes: int = 0
    generated_data_classes: int = 0

    @property
    def main_widget_generated(self) -> int:
        return self.generated_properties + self.generated_events + self.sub_control_features

    @property
    def main_widget_coverage(self) -> float:
        """Coverage of main widget params (properties + events)."""
        if self.total_params_main == 0:
            return 100.0
        return self.main_widget_generated / self.total_params_main * 100

    @property
    def widget_class_coverage(self) -> float:
        """How many widget classes were processed."""
        if self.total_widget_classes == 0:
            return 100.0
        return self.processed_widget_classes / self.total_widget_classes * 100

    @property
    def enum_coverage(self) -> float:
        """Dart enums mapped to Python enums."""
        if self.total_dart_enums == 0:
            return 100.0
        return self.generated_enums / self.total_dart_enums * 100

    @property
    def overall_feature_coverage(self) -> float:
        """Weighted overall coverage across all dimensions.

        Weights: params 60%, enums 20%, widget classes 20%.
        """
        w_params = 0.6
        w_enums = 0.2
        w_classes = 0.2
        return (
            self.main_widget_coverage * w_params
            + self.enum_coverage * w_enums
            + self.widget_class_coverage * w_classes
        )

    def summary(self) -> str:
        lines = [
            f"  Package: {self.flutter_package}",
            f"  Main widget: {self.main_widget}",
            "",
            f"  Widget classes: {self.processed_widget_classes}"
            f"/{self.total_widget_classes}"
            f" ({self.widget_class_coverage:.0f}%)",
            f"  Main widget params: {self.total_params_main}",
            f"    -> properties: {self.generated_properties}",
            f"    -> events:     {self.generated_events}",
            f"    -> sub-ctrl:   {self.sub_control_features}",
            f"    -> COVERAGE:   {self.main_widget_coverage:.1f}%",
            f"  All widgets params: {self.total_params_all_widgets}",
            f"  Enums: {self.generated_enums}/{self.total_dart_enums} ({self.enum_coverage:.0f}%)",
            f"  Data classes: {self.generated_data_classes}/{self.total_helper_classes}",
            "",
            f"  OVERALL: {self.overall_feature_coverage:.1f}%",
        ]
        return "\n".join(lines)


# -- Helpers ----------------------------------------------------------------


def _count_eligible_params(widget: DartClass) -> int:
    """Count constructor params excluding framework internals."""
    return sum(1 for p in widget.constructor_params if p.name not in _FRAMEWORK_PARAMS)


def _count_sub_control_features(sub_controls) -> int:
    """Recursively count properties + events in sub-controls."""
    total = 0
    for sc in sub_controls:
        total += len(sc.properties) + len(sc.events)
        total += _count_sub_control_features(sc.sub_controls)
    return total


def _count_sub_control_classes(sub_controls) -> int:
    """Recursively count sub-control classes (each is a processed widget)."""
    total = 0
    for sc in sub_controls:
        total += 1
        total += _count_sub_control_classes(sc.sub_controls)
    return total


def _build_coverage_report(
    flutter_package: str,
    api: DartPackageAPI,
    plan: GenerationPlan,
) -> CoverageReport:
    """Build a comprehensive coverage report from parsed API + plan."""
    widget_classes = [c for c in api.classes if c.constructor_params]

    # Find the main widget
    main_widget = next(
        (c for c in widget_classes if c.name == plan.dart_main_class),
        widget_classes[0] if widget_classes else None,
    )

    report = CoverageReport(
        flutter_package=flutter_package,
        main_widget=plan.dart_main_class or "?",
    )

    # Widget class counts
    report.total_widget_classes = len(widget_classes)
    n_sub = _count_sub_control_classes(plan.sub_controls)

    # Family: all widget classes are covered via the enum type
    if plan.widget_family_variants:
        report.processed_widget_classes = len(plan.widget_family_variants)
    # Siblings: main + each sibling
    elif plan.sibling_widgets:
        report.processed_widget_classes = 1 + len(plan.sibling_widgets) + n_sub
    else:
        report.processed_widget_classes = 1 + n_sub  # main + sub-controls

    # Params across ALL widget classes
    report.total_params_all_widgets = sum(_count_eligible_params(w) for w in widget_classes)

    # Main widget params
    # For families, count shared params (intersection) rather than
    # the template's total, since only shared params are generated.
    if plan.widget_family_variants and len(widget_classes) > 1:
        _fw = {"key", "child", "children"}
        param_sets = [
            {p.name for p in w.constructor_params if p.name not in _fw} for w in widget_classes
        ]
        shared = param_sets[0].copy()
        for s in param_sets[1:]:
            shared &= s
        # +1 for the "type" property that the family processor adds
        report.total_params_main = len(shared) + 1
    elif main_widget:
        report.total_params_main = _count_eligible_params(main_widget)

    # Generated features
    report.generated_properties = len(plan.properties)
    report.generated_events = len(plan.events)
    report.sub_control_features = _count_sub_control_features(
        plan.sub_controls,
    )

    # Enums
    report.total_dart_enums = len(api.enums)
    report.generated_enums = len(plan.enums)

    # Helper/data classes
    report.total_helper_classes = len(api.helper_classes)
    report.generated_data_classes = len(plan.stub_data_classes)

    return report


# -- Fixtures ---------------------------------------------------------------


@pytest.fixture(scope="module")
def downloader():
    return PubDevDownloader()


@pytest.fixture(scope="module")
def analyzer():
    return PackageAnalyzer()


# -- Tests ------------------------------------------------------------------


@pytest.mark.parametrize(
    "pkg",
    UI_CONTROL_PACKAGES,
    ids=[p["flutter_package"] for p in UI_CONTROL_PACKAGES],
)
class TestUIControlCoverage:
    def _run_analysis(self, pkg, downloader, analyzer):
        """Download, parse, and analyze a Flutter package."""
        flutter_package = pkg["flutter_package"]
        control_name = pkg["control_name"]
        package_name = f"flet_{flutter_package.removeprefix('flutter_')}"

        package_path = downloader.download(flutter_package)
        api = parse_dart_package_api(package_path, include_widgets=True)
        plan = analyzer.analyze(
            api,
            control_name=control_name,
            extension_type="ui_control",
            flutter_package=flutter_package,
            package_name=package_name,
            description=pkg["description"],
        )
        return api, plan

    def test_main_widget_coverage(self, pkg, downloader, analyzer):
        """Main widget property/event coverage must be >= 70%."""
        api, plan = self._run_analysis(pkg, downloader, analyzer)
        report = _build_coverage_report(pkg["flutter_package"], api, plan)

        print(f"\n{'=' * 60}")
        print(report.summary())
        print(f"{'=' * 60}")

        assert report.main_widget_coverage >= MIN_COVERAGE_PCT, (
            f"{pkg['flutter_package']}: main widget coverage "
            f"{report.main_widget_coverage:.1f}% < {MIN_COVERAGE_PCT}%"
        )

    def test_enum_coverage(self, pkg, downloader, analyzer):
        """All Dart enums in the package should be mapped."""
        api, plan = self._run_analysis(pkg, downloader, analyzer)
        report = _build_coverage_report(pkg["flutter_package"], api, plan)

        if report.total_dart_enums == 0:
            pytest.skip("No enums in this package")

        assert report.enum_coverage >= MIN_COVERAGE_PCT, (
            f"{pkg['flutter_package']}: enum coverage "
            f"{report.enum_coverage:.1f}% < {MIN_COVERAGE_PCT}% "
            f"({report.generated_enums}/{report.total_dart_enums})"
        )

    def test_overall_coverage(self, pkg, downloader, analyzer):
        """Weighted overall coverage must be >= 70%."""
        api, plan = self._run_analysis(pkg, downloader, analyzer)
        report = _build_coverage_report(pkg["flutter_package"], api, plan)

        assert report.overall_feature_coverage >= MIN_COVERAGE_PCT, (
            f"{pkg['flutter_package']}: overall coverage "
            f"{report.overall_feature_coverage:.1f}% < {MIN_COVERAGE_PCT}%"
        )

    def test_produces_output(self, pkg, downloader, analyzer):
        """Pipeline must produce at least some properties or events."""
        api, plan = self._run_analysis(pkg, downloader, analyzer)

        total = (
            len(plan.properties)
            + len(plan.events)
            + len(plan.enums)
            + _count_sub_control_features(plan.sub_controls)
        )
        assert total > 0, f"{pkg['flutter_package']}: nothing generated"
        assert plan.dart_main_class, f"{pkg['flutter_package']}: no main widget"
