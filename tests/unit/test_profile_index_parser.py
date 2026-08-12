"""Unit tests for pure runtime profile output parsing."""

from __future__ import annotations

from openbuds.infrastructure.pipewire.profile_index_parser import (
    parse_profile_index,
    parse_profile_names,
)

_TREE = "\n".join(
    (
        "  Object: size 160, type Spa:Pod:Object:Param:Profile (262151), "
        "id Spa:Enum:ParamId:EnumProfile (8)",
        "    Prop: key Spa:Pod:Object:Param:Profile:index (1), flags 00000000",
        "      Int 0",
        "    Prop: key Spa:Pod:Object:Param:Profile:name (2), flags 00000000",
        '      String "off"',
        "    Prop: key Spa:Pod:Object:Param:Profile:description (3), flags 00000000",
        '      String "Apagado"',
        "  Object: size 432, type Spa:Pod:Object:Param:Profile (262151), "
        "id Spa:Enum:ParamId:EnumProfile (8)",
        "    Prop: key Spa:Pod:Object:Param:Profile:index (1), flags 00000000",
        "      Int 1",
        "    Prop: key Spa:Pod:Object:Param:Profile:name (2), flags 00000000",
        '      String "a2dp-sink"',
        "  Object: size 300, type Spa:Pod:Object:Param:Profile (262151), "
        "id Spa:Enum:ParamId:EnumProfile (8)",
        "    Prop: key Spa:Pod:Object:Param:Profile:index (1), flags 00000000",
        "      Int 2",
        "    Prop: key Spa:Pod:Object:Param:Profile:name (2), flags 00000000",
        '      String "headset-head-unit-msbc"',
    )
)


def test_parse_profile_index_accepts_lines_with_and_without_id() -> None:
    output = "\n".join(
        (
            "index:0 id:0 name:off",
            "index:1 name:a2dp-sink",
            "index:2 id:2 name:headset-head-unit-msbc",
        )
    )

    assert parse_profile_index(output, "a2dp-sink") == 1
    assert parse_profile_index(output, "headset-head-unit-msbc") == 2


def test_parse_profile_index_parses_pw_cli_tree_format() -> None:
    assert parse_profile_index(_TREE, "a2dp-sink") == 1
    assert parse_profile_index(_TREE, "headset-head-unit-msbc") == 2
    assert parse_profile_index(_TREE, "off") == 0


def test_parse_profile_names_preserves_tree_order() -> None:
    assert parse_profile_names(_TREE) == ("off", "a2dp-sink", "headset-head-unit-msbc")


def test_parse_profile_index_returns_none_for_missing_name() -> None:
    assert parse_profile_index("index:0 id:0 name:off", "a2dp-sink") is None
    assert parse_profile_index(_TREE, "ldac") is None


def test_parse_profile_names_preserves_reported_order() -> None:
    output = "index:3 name:first\nindex:1 id:1 name:second\n"

    assert parse_profile_names(output) == ("first", "second")
