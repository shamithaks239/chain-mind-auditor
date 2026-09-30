class ChainMindError(Exception):
    pass


class InvalidAddressError(ChainMindError):
    pass


class EtherscanError(ChainMindError):
    pass


class EtherscanRateLimitError(EtherscanError):
    pass


class NotVerifiedError(ChainMindError):
    pass


class SanitizationError(ChainMindError):
    pass


class OllamaError(ChainMindError):
    pass


class OllamaUnavailableError(OllamaError):
    pass


class ModelNotInstalledError(OllamaError):
    pass