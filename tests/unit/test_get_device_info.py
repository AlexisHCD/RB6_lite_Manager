"""Tests for the aggregated device information use case."""

from __future__ import annotations

from openbuds.application.get_device_info import GetDeviceInfoUseCase
from openbuds.domain.enums import AddressType, BluetoothProfile, CodecType, DeviceIcon
from openbuds.domain.models import BluetoothAudioNode, CodecInfo, DeviceInfo

ADDRESS = "00:11:22:33:44:55"
PATH = "/org/bluez/hci0/dev_00_11_22_33_44_55"


def _device() -> DeviceInfo:
    return DeviceInfo(
        object_path=PATH,
        address=ADDRESS,
        name="Buds",
        alias="Buds",
        icon=DeviceIcon.UNKNOWN,
        address_type=AddressType.UNKNOWN,
        paired=True,
        connected=True,
        trusted=False,
        blocked=False,
        services_resolved=False,
    )


class FakeBluetoothRepository:
    def __init__(self, device: DeviceInfo | None) -> None:
        self.device = device

    def get_device(self, path: str) -> DeviceInfo | None:
        return self.device if path == PATH else None

    def get_battery(self, _path: str) -> None:
        return None

    def get_rssi(self, _path: str) -> None:
        return None


class FakeAudioRepository:
    def __init__(self, codec: CodecInfo | None, nodes: list[BluetoothAudioNode]) -> None:
        self.codec = codec
        self.nodes = nodes

    def get_active_codec(self, _address: str) -> CodecInfo | None:
        return self.codec

    def list_device_audio_nodes(self, _address: str) -> list[BluetoothAudioNode]:
        return self.nodes


def _execute(
    device: DeviceInfo | None = None,
    codec: CodecInfo | None = None,
    nodes: list[BluetoothAudioNode] | None = None,
):
    return GetDeviceInfoUseCase(
        FakeBluetoothRepository(device), FakeAudioRepository(codec, nodes or [])
    ).execute(PATH)


def test_missing_device_returns_none() -> None:
    assert _execute() is None


def test_device_without_audio_returns_empty_optional_state() -> None:
    result = _execute(_device())

    assert result is not None
    assert result.audio_nodes == ()
    assert result.codec is None
    assert result.battery is None
    assert result.rssi is None


def test_device_with_sink_aggregates_observed_codec_and_transport() -> None:
    codec = CodecInfo(CodecType.SBC, BluetoothProfile.A2DP, verified=True)
    node = BluetoothAudioNode("sink", "Audio/Sink", "a2dp-sink", "sbc", "")

    result = _execute(_device(), codec, [node])

    assert result is not None
    assert result.codec == codec
    assert result.audio_nodes == (node,)


def test_off_profile_has_no_active_codec() -> None:
    result = _execute(_device(), None, [BluetoothAudioNode("off", "", "off", "sbc", "")])

    assert result is not None
    assert result.codec is None


def test_unknown_codec_is_unverified() -> None:
    codec = CodecInfo(CodecType.UNKNOWN, BluetoothProfile.A2DP, verified=False)

    assert _execute(_device(), codec).codec == codec
