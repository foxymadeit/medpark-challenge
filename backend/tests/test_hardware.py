import hardware


def test_the_machine_picks_the_profile():
    assert hardware.detect(gpu_gb=16, ram_gb=8, apple=False) == "gpu"
    assert hardware.detect(gpu_gb=0, ram_gb=32, apple=False) == "cpu"
    assert hardware.detect(gpu_gb=6, ram_gb=16, apple=False) == "laptop"
    assert hardware.detect(gpu_gb=0, ram_gb=24, apple=True) == "mac"
    assert hardware.detect(gpu_gb=0, ram_gb=16, apple=True) == "laptop"   # too little memory for gpt-oss:20b


def test_settings_in_the_environment_win(monkeypatch):
    monkeypatch.setenv("MOM_LLM_MODEL", "gemma3:12b")
    env = hardware.stage_env("gpu")
    assert "MOM_LLM_MODEL" not in env and env["MOM_DEVICE"] == "cuda"


def test_a_named_profile_overrides_detection(monkeypatch):
    monkeypatch.setenv("LIMINAL_PROFILE", "laptop")
    assert hardware.profile() == "laptop"


def test_minutes_made_elsewhere_are_found_under_the_work_folder(tmp_path):
    import jobs
    assert jobs.minutes_folder(tmp_path) == tmp_path / "minutes"            # nothing yet: the usual place
    remote = tmp_path / "kaggle-out" / "minutes"
    remote.mkdir(parents=True)
    (remote / "MoM_2026-09-26_medical.facts.json").write_text("{}")
    assert jobs.minutes_folder(tmp_path) == remote                          # a remote run's own layout
    (tmp_path / "minutes").mkdir()
    (tmp_path / "minutes" / "MoM_2026-09-26_medical.facts.json").write_text("{}")
    assert jobs.minutes_folder(tmp_path) == tmp_path / "minutes"            # the usual place wins
