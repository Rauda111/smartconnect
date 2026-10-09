"""Intentionally simple Strongest Signal First baseline; no SmartConnect logic."""


def select_network(wifi_rssi, g5_rssi):
    """Choose the larger RSSI in dBm (-50 > -70); ties choose WiFi."""
    return "WiFi" if wifi_rssi >= g5_rssi else "5G"


def apply_baseline(trace):
    """Return a copy with selections and handovers; never mutate the input trace.

    Initial attachment is not a handover. A handover is a change from the
    previous row's selected network, with no hysteresis or dwell time.
    """
    result = trace.copy(deep=True)
    result["selected_network"] = [
        select_network(wifi, g5)
        for wifi, g5 in zip(result["wifi_rssi"], result["g5_rssi"])
    ]
    previous = result["selected_network"].shift()
    result["handover"] = previous.notna() & result["selected_network"].ne(previous)
    return result
