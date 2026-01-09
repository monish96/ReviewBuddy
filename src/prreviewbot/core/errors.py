class PRReviewBotError(Exception):
    pass


class UnsupportedHostError(PRReviewBotError):
    pass


class AuthRequiredError(PRReviewBotError):
    def __init__(self, provider: str, host: str, message: str = "Authentication required"):
        super().__init__(message)
        self.provider = provider
        self.host = host


class ProviderError(PRReviewBotError):
    pass


