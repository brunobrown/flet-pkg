from flet_pkg.core.validators import (
    derive_names,
    validate_control_name,
    validate_flutter_package,
    validate_package_name,
    validate_project_name,
)


class TestValidatePackageName:
    def test_valid(self):
        assert validate_package_name("flet_onesignal") is None

    def test_valid_simple(self):
        assert validate_package_name("mypkg") is None

    def test_invalid_uppercase(self):
        assert validate_package_name("FletPkg") is not None

    def test_invalid_hyphen(self):
        assert validate_package_name("flet-pkg") is not None

    def test_invalid_starts_with_number(self):
        assert validate_package_name("1pkg") is not None

    def test_empty(self):
        assert validate_package_name("") is not None


class TestValidateProjectName:
    def test_valid(self):
        assert validate_project_name("flet-onesignal") is None

    def test_invalid_uppercase(self):
        assert validate_project_name("Flet-Onesignal") is not None

    def test_invalid_underscore(self):
        assert validate_project_name("flet_onesignal") is not None


class TestValidateFlutterPackage:
    def test_valid(self):
        assert validate_flutter_package("onesignal_flutter") is None

    def test_invalid(self):
        assert validate_flutter_package("OneSignal-Flutter") is not None


class TestValidateControlName:
    def test_valid(self):
        assert validate_control_name("OneSignal") is None

    def test_valid_simple(self):
        assert validate_control_name("Spinkit") is None

    def test_invalid_lowercase(self):
        assert validate_control_name("oneSignal") is not None

    def test_invalid_underscore(self):
        assert validate_control_name("One_Signal") is not None


class TestDeriveNames:
    def test_flutter_suffix(self):
        names = derive_names("onesignal_flutter")
        assert names.project_name == "flet-onesignal"
        assert names.package_name == "flet_onesignal"
        assert names.control_name == "Onesignal"
        assert names.control_name_snake == "onesignal"

    def test_flutter_prefix(self):
        names = derive_names("flutter_spinkit")
        assert names.project_name == "flet-spinkit"
        assert names.package_name == "flet_spinkit"
        assert names.control_name == "Spinkit"
        assert names.control_name_snake == "spinkit"

    def test_multi_word(self):
        names = derive_names("google_maps_flutter")
        assert names.project_name == "flet-google-maps"
        assert names.package_name == "flet_google_maps"
        assert names.control_name == "GoogleMaps"
        assert names.control_name_snake == "google_maps"

    def test_no_suffix(self):
        names = derive_names("audioplayers")
        assert names.project_name == "flet-audioplayers"
        assert names.package_name == "flet_audioplayers"
        assert names.control_name == "Audioplayers"
