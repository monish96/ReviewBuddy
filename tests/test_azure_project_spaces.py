import respx

from prreviewbot.providers.azure_devops import AzureDevOpsProvider
from prreviewbot.providers.base import ProviderContext


@respx.mock
def test_azure_project_name_with_spaces_is_encoded():
    # Project contains spaces in the PR URL path
    pr_url = "https://dev.azure.com/org/OTA Update Path Tool/_git/repo/pullrequest/42"

    # Provider should encode spaces as %20 when calling _apis
    respx.get(
        "https://dev.azure.com/org/OTA%20Update%20Path%20Tool/_apis/git/repositories/repo/pullRequests/42",
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
    respx.get(
        "https://dev.azure.com/org/OTA%20Update%20Path%20Tool/_apis/git/repositories/repo/pullRequests/42/iterations",
        params__contains={"api-version": "7.1-preview.1"},
    ).respond(200, json={"value": [{"id": 1}]})
    respx.get(
        "https://dev.azure.com/org/OTA%20Update%20Path%20Tool/_apis/git/repositories/repo/pullRequests/42/iterations/1/changes",
        params__contains={"api-version": "7.1-preview.1"},
    ).respond(200, json={"changeEntries": []})
    respx.get(
        "https://dev.azure.com/org/OTA%20Update%20Path%20Tool/_apis/git/repositories/repo/pullRequests/42/threads",
        params__contains={"api-version": "7.1-preview.1"},
    ).respond(200, json={"value": []})

    p = AzureDevOpsProvider()
    info = p.fetch_pr(ProviderContext(pr_url=pr_url, token="pat"))
    assert info.title == "t"


