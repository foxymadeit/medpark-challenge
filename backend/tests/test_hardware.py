import hardware


def test_the_machine_picks_the_profile():
    assert hardware.detect(gpu_gb=16, ram_gb=8) == "gpu"
    assert hardware.detect(gpu_gb=0, ram_gb=32) == "cpu"
    assert hardware.detect(gpu_gb=6, ram_gb=16) == "laptop"


def test_settings_in_the_environment_win(monkeypatch):
    monkeypatch.setenv("MOM_LLM_MODEL", "gemma3:12b")
    env = hardware.stage_env("gpu")
    assert "MOM_LLM_MODEL" not in env and env["MOM_DEVICE"] == "cuda"


def test_a_named_profile_overrides_detection(monkeypatch):
    monkeypatch.setenv("LIMINAL_PROFILE", "laptop")
    assert hardware.profile() == "laptop"
