import respx

from prreviewbot.core.errors import ProviderError
from prreviewbot.providers.azure_devops import AzureDevOpsProvider
from prreviewbot.providers.base import ProviderContext


@respx.mock
def test_azure_items_invalid_json_becomes_provider_error():
    # PR metadata + changes return JSON
    respx.get(
        "https://dev.azure.com/org/proj/_apis/git/repositories/repo/pullRequests/42",
        params__contains={"api-version": "7.1-preview.1"},
    ).respond(
        200,
        json={
            "title": "t",
            "description": "d",
            "lastMergeSourceCommit": {"commitId": "src"},
            "lastMergeTargetCommit": {"commitId": "dst"},
        },
    )
    # iterations list
    respx.get(
        "https://dev.azure.com/org/proj/_apis/git/repositories/repo/pullRequests/42/iterations",
        params__contains={"api-version": "7.1-preview.1"},
    ).respond(200, json={"value": [{"id": 1}]})
    # iteration changes
    respx.get(
        "https://dev.azure.com/org/proj/_apis/git/repositories/repo/pullRequests/42/iterations/1/changes",
        params__contains={"api-version": "7.1-preview.1"},
    ).respond(200, json={"changeEntries": [{"item": {"path": "/a.txt"}}]})

    # items endpoint claims JSON but returns invalid body -> should not crash as JSONDecodeError
    respx.get(
        "https://dev.azure.com/org/proj/_apis/git/repositories/repo/items",
    ).respond(
        200,
        text="not json",
        headers={"content-type": "application/json"},
    )

    p = AzureDevOpsProvider()
    try:
        p.fetch_pr(
            ProviderContext(
                pr_url="https://dev.azure.com/org/proj/_git/repo/pullrequest/42",
                token="pat",
            )
        )
        assert False, "expected ProviderError"
    except ProviderError:
        pass


