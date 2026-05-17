"""Shared exception hierarchy for agent-level errors."""


class SSLConfigurationError(RuntimeError):
    """Raised when the TLS CA certificate bundle is missing, empty, or unloadable.

    This typically happens after a ``git pull`` that updated source code
    without reinstalling the virtual environment, leaving ``certifi``s
    bundled :file:`cacert.pem` out of sync with its package metadata.

    The ``instruction`` attribute carries a short, user-actionable hint.
    """

    DEFAULT_INSTRUCTION = (
        "Run:  pip install -e .\n"
        "Doc:  docs/rca-ssl-cacert-post-git-pull.md"
    )

    def __init__(self, message: str, *, instruction: str | None = None) -> None:
        super().__init__(message)
        self.instruction = instruction or self.DEFAULT_INSTRUCTION

    def __str__(self) -> str:
        if self.instruction:
            return f"{self.args[0]}\n\n{self.instruction}"
        return super().__str__()
