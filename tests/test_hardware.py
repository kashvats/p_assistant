from living_assistant.hardware import HardwareInfo, choose_profile

CFG = {"profile":"auto"}

def hw(ram):
    return HardwareInfo("Linux","x86_64",4,8,ram,ram-1)

def test_profiles():
    assert choose_profile(CFG, hw(8)) == "lite"
    assert choose_profile(CFG, hw(32)) == "balanced"
    assert choose_profile(CFG, hw(64)) == "power"
