"""Contract for runtime audio profile changes."""

from __future__ import annotations


class IAudioControlRepository:
    """Control only profiles actually offered by the system.

    Operations are runtime and non-persistent. User approval is required before
    execution against a real system.
    """

    def list_profiles(self, device_address: str) -> tuple[str, ...]:
        """Return runtime profiles offered for the device."""
        raise NotImplementedError

    def set_profile(self, device_address: str, profile_name: str) -> None:
        """Activate an offered runtime profile for the device."""
        raise NotImplementedError
