import respx

from prreviewbot.core.errors import AuthRequiredError
from prreviewbot.providers.azure_devops import AzureDevOpsProvider
from prreviewbot.providers.base import ProviderContext


@respx.mock
def test_azure_provider_html_means_auth_required():
    # Match any Azure DevOps API call and return HTML with 200
    respx.get(url__regex=r"^https://dev\.azure\.com/.+/_apis/.+$").respond(
        200,
        text="<!doctype html><html><body>Sign in</body></html>",
        headers={"content-type": "text/html; charset=utf-8"},
    )

    p = AzureDevOpsProvider()
    try:
        p.fetch_pr(
            ProviderContext(
                pr_url="https://dev.azure.com/org/proj/_git/repo/pullrequest/42",
                token="pat",
            )
        )
        assert False, "expected AuthRequiredError"
    except AuthRequiredError as e:
        assert e.provider == "azure"


