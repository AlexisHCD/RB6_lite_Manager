"""Contract for controlling user-level systemd services."""

from __future__ import annotations


class IUserServiceController:
    """Control user services without using sudo or system units."""

    def start(self, units: tuple[str, ...]) -> None:
        """Start user systemd units idempotently."""
        raise NotImplementedError

    def is_active(self, unit: str) -> bool:
        """Return whether a user systemd unit is active."""
        raise NotImplementedError
