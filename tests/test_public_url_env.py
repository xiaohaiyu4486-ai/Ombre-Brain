from utils import load_config


def test_load_config_applies_public_url_environment_override(monkeypatch, tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "deployment:\n  public_url: https://saved.example\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(
        "OMBRE_PUBLIC_URL", "https://ombre-brain-claude.onrender.com"
    )

    config = load_config(str(config_path))

    assert config["deployment"]["public_url"] == (
        "https://ombre-brain-claude.onrender.com"
    )
