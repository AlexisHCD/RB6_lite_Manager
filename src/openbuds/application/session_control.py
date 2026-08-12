"""Use cases for explicit Bluetooth connection and audio profile actions."""

from __future__ import annotations

from dataclasses import dataclass

from openbuds.core.errors import ProfileUnavailableError
from openbuds.domain.enums import BluetoothProfile
from openbuds.domain.interfaces import IAudioControlRepository, IBluetoothRepository


@dataclass(frozen=True, slots=True)
class ConnectDeviceRequest:
    """Parameters for connecting one paired device."""

    device_path: str


@dataclass(frozen=True, slots=True)
class DisconnectDeviceRequest:
    """Parameters for disconnecting one connected device."""

    device_path: str


@dataclass(frozen=True, slots=True)
class SetAudioProfileRequest:
    """Parameters for one runtime Bluetooth audio profile change."""

    device_address: str
    profile: BluetoothProfile


class ConnectDeviceUseCase:
    """Connect a device through the official BlueZ API.

    Real execution requires prior user approval at the presentation boundary.
    """

    def __init__(self, bluetooth_repo: IBluetoothRepository) -> None:
        self._bluetooth = bluetooth_repo

    def execute(self, request: ConnectDeviceRequest) -> None:
        """Connect the requested device."""
        self._bluetooth.connect(request.device_path)


class DisconnectDeviceUseCase:
    """Disconnect a device through the official BlueZ API.

    Real execution requires prior user approval at the presentation boundary.
    """

    def __init__(self, bluetooth_repo: IBluetoothRepository) -> None:
        self._bluetooth = bluetooth_repo

    def execute(self, request: DisconnectDeviceRequest) -> None:
        """Disconnect the requested device."""
        self._bluetooth.disconnect(request.device_path)


class SetAudioProfileUseCase:
    """Select an offered, non-persistent Bluetooth audio profile.

    The CLI must obtain user approval before invoking this mutation.
    """

    def __init__(self, audio_control_repo: IAudioControlRepository) -> None:
        self._audio = audio_control_repo

    def execute(self, request: SetAudioProfileRequest) -> str:
        """Apply the requested runtime profile and return its system name."""
        if request.profile is BluetoothProfile.A2DP:
            target = "a2dp-sink"
        elif request.profile is BluetoothProfile.HFP:
            offered = self._audio.list_profiles(request.device_address)
            if "headset-head-unit-msbc" in offered:
                target = "headset-head-unit-msbc"
            elif "headset-head-unit" in offered:
                target = "headset-head-unit"
            else:
                raise ProfileUnavailableError(
                    "el sistema no ofrece perfil HFP para este dispositivo"
                )
        else:
            raise ValueError("unsupported Bluetooth audio profile")

        self._audio.set_profile(request.device_address, target)
        return target
