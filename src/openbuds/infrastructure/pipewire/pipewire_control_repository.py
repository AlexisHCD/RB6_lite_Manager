"""Runtime Bluetooth audio profile control through PipeWire and WirePlumber."""

from __future__ import annotations

from openbuds.core.errors import ProfileUnavailableError
from openbuds.domain.interfaces import IAudioControlRepository
from openbuds.infrastructure.pipewire.node_mapper import normalize_address
from openbuds.infrastructure.pipewire.profile_index_parser import (
    parse_profile_index,
    parse_profile_names,
)
from openbuds.infrastructure.pipewire.pw_cli_runner import PwCliRunner
from openbuds.infrastructure.pipewire.pw_dump_parser import parse_bluetooth_device_ids
from openbuds.infrastructure.pipewire.pw_dump_runner import PwDumpRunner
from openbuds.infrastructure.wireplumber.wpctl_adapter import WpctlAdapter


class PipeWireControlRepository(IAudioControlRepository):
    """List and change only runtime profiles offered by PipeWire."""

    def __init__(
        self,
        runner: PwDumpRunner | None = None,
        cli_runner: PwCliRunner | None = None,
        wpctl: WpctlAdapter | None = None,
    ) -> None:
        self._runner = runner if runner is not None else PwDumpRunner()
        self._cli_runner = cli_runner if cli_runner is not None else PwCliRunner()
        self._wpctl = wpctl if wpctl is not None else WpctlAdapter()

    def list_profiles(self, device_address: str) -> tuple[str, ...]:
        """Return profiles offered for one Bluetooth address."""
        device_id = self._device_id(device_address)
        if device_id is None:
            return ()
        return parse_profile_names(self._cli_runner.enum_params(device_id))

    def set_profile(self, device_address: str, profile_name: str) -> None:
        """Set one offered profile for the current runtime session."""
        device_id = self._device_id(device_address)
        if device_id is None:
            raise ProfileUnavailableError("el dispositivo no tiene una tarjeta de audio disponible")

        output = self._cli_runner.enum_params(device_id)
        profile_index = parse_profile_index(output, profile_name)
        if profile_index is None:
            raise ProfileUnavailableError(f"perfil '{profile_name}' no ofrecido por el sistema")
        self._wpctl.set_profile(device_id, profile_index)

    def _device_id(self, device_address: str) -> int | None:
        """Resolve one address to a PipeWire device object ID."""
        device_ids = parse_bluetooth_device_ids(self._runner.dump())
        return device_ids.get(normalize_address(device_address))
