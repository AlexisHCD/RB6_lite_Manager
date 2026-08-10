"""Pruebas del perfil Redmi Buds 6 Lite."""

from profiles.redmi_buds_6_lite import RedmiBuds6LiteProfile, match_device


def test_match_device_accepts_variants() -> None:
    assert match_device("REDMI BUDS 6 LITE")
    assert match_device("Redmi Buds 6")


def test_match_device_rejects_other_devices() -> None:
    assert not match_device("Redmi Buds 5")


def test_profile_is_conservative_and_frozen() -> None:
    profile = RedmiBuds6LiteProfile()
    assert profile.default_profile == "A2DP"
    assert "SBC" in profile.supported_codecs
