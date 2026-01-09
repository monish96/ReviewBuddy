from prreviewbot.llm.openai_llm import _safe_json as openai_safe_json
from prreviewbot.llm.azure_openai_llm import _safe_json as custom_safe_json


def test_safe_json_parses_json_fence_with_language_tag():
    s = """```json
{"summary":["a","b"],"comments":[{"file_path":"x","severity":"warn","message":"m"}]}
```"""
    j1 = openai_safe_json(s)
    j2 = custom_safe_json(s)
    assert j1 and j1["summary"] == ["a", "b"]
    assert j2 and j2["comments"][0]["file_path"] == "x"


