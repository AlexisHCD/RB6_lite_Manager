"""Tests de los modelos del dominio (dataclasses e invariantes)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from openbuds.domain.enums import AddressType, BluetoothProfile, CodecType, DeviceIcon
from openbuds.domain.models import (
    BatteryLevel,
    CodecInfo,
    DeviceInfo,
    RSSIReading,
)


class TestBatteryLevel:
    def test_valid_percentage(self) -> None:
        b = BatteryLevel(percentage=80, source="GATT Battery Service")
        assert b.percentage == 80
        assert b.source == "GATT Battery Service"

    def test_none_percentage_allowed(self) -> None:
        b = BatteryLevel(percentage=None)
        assert b.percentage is None

    @pytest.mark.parametrize("invalid", [-1, 101, 150])
    def test_out_of_range_raises(self, invalid: int) -> None:
        with pytest.raises(ValueError):
            BatteryLevel(percentage=invalid)


class TestRSSIReading:
    def test_valid_negative_rssi(self) -> None:
        r = RSSIReading(rssi_dbm=-67, timestamp=datetime.now(tz=UTC))
        assert r.rssi_dbm == -67

    def test_positive_rssi_raises(self) -> None:
        with pytest.raises(ValueError):
            RSSIReading(rssi_dbm=10, timestamp=datetime.now(tz=UTC))

    def test_none_rssi_allowed(self) -> None:
        r = RSSIReading(rssi_dbm=None, timestamp=datetime.now(tz=UTC))
        assert r.rssi_dbm is None


class TestDeviceInfo:
    def test_construction_with_defaults(self) -> None:
        d = DeviceInfo(
            object_path="/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF",
            address="AA:BB:CC:DD:EE:FF",
            name="Redmi Buds 6 Lite",
            alias="Redmi Buds 6 Lite",
            icon=DeviceIcon.AUDIO_CARD,
            address_type=AddressType.PUBLIC,
            paired=True,
            connected=True,
            trusted=True,
            blocked=False,
            services_resolved=True,
        )
        assert d.uuids == ()
        assert d.adapter_path == ""


class TestCodecInfo:
    def test_unverified_vendor_codec_flag(self) -> None:
        # aptX es vendor endpoint no canonizado: debe marcarse no verificado.
        c = CodecInfo(
            codec=CodecType.APTX,
            profile=BluetoothProfile.A2DP,
            a2dp_codec_byte=None,
            verified=False,
        )
        assert c.verified is False

    def test_sbc_is_verified_by_default(self) -> None:
        c = CodecInfo(codec=CodecType.SBC, profile=BluetoothProfile.A2DP)
        assert c.verified is True
