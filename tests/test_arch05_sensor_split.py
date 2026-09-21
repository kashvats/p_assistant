from __future__ import annotations

import living_assistant.security_sensors as sensors
from living_assistant.security import sensors_macos, sensors_windows


def test_platform_sensor_collectors_are_split_but_public_contract_is_preserved():
    assert sensors.collect_windows_eventlog is sensors_windows.collect_windows_eventlog
    assert sensors.collect_macos_unified_log is sensors_macos.collect_macos_unified_log
    assert sensors.normalize_sysmon_event is sensors_windows.normalize_sysmon_event
    assert sensors.SYSMON_CHANNEL == sensors_windows.SYSMON_CHANNEL
    assert sensors_windows.collect_windows_eventlog.__module__ == "living_assistant.security.sensors_windows"
    assert sensors_macos.collect_macos_unified_log.__module__ == "living_assistant.security.sensors_macos"
