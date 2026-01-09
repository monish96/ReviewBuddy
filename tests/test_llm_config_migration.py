import json

from prreviewbot.storage.config import ConfigStore


def test_llm_migration_azure_openai_keys_to_openai(tmp_path):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(
        json.dumps(
            {
                "llm": {
                    "provider": "azure_openai",
                    "azure_openai_endpoint": "https://genai-nexus.api.corpinter.net/apikey/",
                    "azure_openai_api_key": "k",
                    "azure_openai_api_version": "2024-02-15-preview",
                    "azure_openai_deployment": "dep",
                }
            }
        ),
        encoding="utf-8",
    )
    store = ConfigStore(data_dir=tmp_path)
    cfg = store.load()
    assert cfg.llm.get("provider") == "openai"
    assert cfg.llm.get("openai_endpoint") == "https://genai-nexus.api.corpinter.net/apikey/"
    assert cfg.llm.get("openai_api_key") == "k"
    assert cfg.llm.get("openai_api_version") == "2024-02-15-preview"
    assert cfg.llm.get("openai_deployment") == "dep"


