import pytest

from prreviewbot.core.errors import PRReviewBotError
from prreviewbot.core.types import ChangedFile
from prreviewbot.llm.openai_llm import OpenAILLM


def test_openai_missing_dependency_raises_clear_error(monkeypatch):
    # Simulate missing openai package even if installed in some environments.
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "openai":
            raise ModuleNotFoundError("No module named 'openai'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    llm = OpenAILLM(api_key="x", model="gpt-4o-mini")
    with pytest.raises(PRReviewBotError) as e:
        llm.review(pr_url="x", language="python", files=[ChangedFile(path="a.py", patch="")], discussion=[])
    assert "OpenAI support is not installed" in str(e.value)


