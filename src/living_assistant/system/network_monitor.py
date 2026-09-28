from __future__ import annotations

from dataclasses import dataclass, field
import datetime as dt
import socket
import psutil
from typing import Any, Callable


@dataclass
class NetworkState:
    online: bool
    interfaces: list[str]
    vpn_active: bool
    dns_resolved: bool
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "online": self.online,
            "interfaces": self.interfaces,
            "vpn_active": self.vpn_active,
            "dns_resolved": self.dns_resolved,
            "timestamp": self.timestamp,
        }


class NetworkMonitor:
    """Monitors dynamic network state, online/offline transitions, and interface changes."""

    def __init__(
        self,
        event_bus: Any = None,
        connectivity_probe: Callable[[], bool] | None = None,
    ):
        self.event_bus = event_bus
        self._custom_probe = connectivity_probe
        self._last_state: NetworkState | None = None
        self._transition_history: list[dict[str, Any]] = []

    def probe_connectivity(self) -> tuple[bool, bool]:
        """Returns (is_online, dns_resolved)."""
        if self._custom_probe is not None:
            try:
                ok = bool(self._custom_probe())
                return ok, ok
            except Exception:
                return False, False

        dns_resolved = False
        try:
            # Check fast DNS resolution against a major resolver
            socket.getaddrinfo("1.1.1.1", 53, socket.AF_INET, socket.SOCK_STREAM)
            dns_resolved = True
        except (socket.error, OSError):
            dns_resolved = False

        # Check raw socket probe to loopback or known public root
        online = dns_resolved
        if not online:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.settimeout(1.0)
                # Does not actually connect/send packets; retrieves outbound interface IP
                s.connect(("8.8.8.8", 80))
                s.close()
                online = True
            except Exception:
                online = False

        return online, dns_resolved

    def scan_interfaces(self) -> tuple[list[str], bool]:
        """Scan active network interfaces and detect VPNs/virtual adapters."""
        active_ifaces = []
        vpn_active = False
        try:
            addrs = psutil.net_if_addrs()
            stats = psutil.net_if_stats()
            vpn_markers = ("vpn", "tun", "tap", "wireguard", "wg", "tailscale", "zerotier", "nord", "openvpn")

            for name, stat in stats.items():
                if stat.isup and name in addrs:
                    active_ifaces.append(name)
                    lower_name = name.lower()
                    if any(marker in lower_name for marker in vpn_markers):
                        vpn_active = True
        except Exception:
            pass

        return sorted(active_ifaces), vpn_active

    def current_state(self) -> NetworkState:
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        online, dns = self.probe_connectivity()
        ifaces, vpn = self.scan_interfaces()
        return NetworkState(
            online=online,
            interfaces=ifaces,
            vpn_active=vpn,
            dns_resolved=dns,
            timestamp=now,
        )

    def is_online(self) -> bool:
        return self.current_state().online

    def check_transition(self) -> dict[str, Any]:
        """Compare current network state with previous scan and emit transition events."""
        current = self.current_state()
        prev = self._last_state
        self._last_state = current

        if prev is None:
            return {
                "transition_detected": False,
                "transition_type": "initial",
                "state": current.to_dict(),
            }

        transition_type = "none"
        if not prev.online and current.online:
            transition_type = "offline_to_online"
        elif prev.online and not current.online:
            transition_type = "online_to_offline"
        elif prev.vpn_active != current.vpn_active:
            transition_type = "vpn_toggled"
        elif prev.interfaces != current.interfaces:
            transition_type = "interface_changed"
        elif prev.dns_resolved != current.dns_resolved:
            transition_type = "dns_changed"

        transition_detected = transition_type != "none"
        record = {
            "transition_detected": transition_detected,
            "transition_type": transition_type,
            "previous_state": prev.to_dict(),
            "state": current.to_dict(),
        }

        if transition_detected:
            self._transition_history.append(record)
            if self.event_bus and hasattr(self.event_bus, "publish"):
                try:
                    self.event_bus.publish(
                        "network.transition",
                        transition_type=transition_type,
                        online=current.online,
                        vpn_active=current.vpn_active,
                    )
                except Exception:
                    pass

        return record

    def status(self) -> dict[str, Any]:
        state = self._last_state or self.current_state()
        return {
            "online": state.online,
            "vpn_active": state.vpn_active,
            "dns_resolved": state.dns_resolved,
            "interfaces": state.interfaces,
            "transition_count": len(self._transition_history),
            "last_transition": self._transition_history[-1] if self._transition_history else None,
        }
