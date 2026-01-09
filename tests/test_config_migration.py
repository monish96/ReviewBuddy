import json

from prreviewbot.storage.config import ConfigStore


def test_token_host_migration_dedup(tmp_path):
    # Simulate an old config with a confusing host key including scheme
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(
        json.dumps(
            {
                "tokens": {
                    "azure": {
                        "https://dev.azure.com": "pat1",
                        "dev.azure.com": "pat2",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    store = ConfigStore(data_dir=tmp_path)
    cfg = store.load()
    # Should dedupe and keep canonical key
    assert "azure" in cfg.tokens
    assert list(cfg.tokens["azure"].keys()) == ["dev.azure.com"]
    assert cfg.tokens["azure"]["dev.azure.com"] == "pat2"


