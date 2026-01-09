from __future__ import annotations

from prreviewbot.core.link_parser import ParsedLink
from prreviewbot.providers.azure_devops import AzureDevOpsProvider
from prreviewbot.providers.bitbucket import BitbucketCloudProvider
from prreviewbot.providers.gitea import GiteaProvider
from prreviewbot.providers.github import GitHubProvider
from prreviewbot.providers.gitlab import GitLabProvider


def provider_for(parsed: ParsedLink):
    if parsed.provider == "github":
        return GitHubProvider()
    if parsed.provider == "gitlab":
        return GitLabProvider()
    if parsed.provider == "bitbucket":
        return BitbucketCloudProvider()
    if parsed.provider == "azure":
        return AzureDevOpsProvider()
    if parsed.provider == "gitea":
        return GiteaProvider()
    raise ValueError(f"Unknown provider: {parsed.provider}")


