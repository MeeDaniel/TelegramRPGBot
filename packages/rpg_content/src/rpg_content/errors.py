"""Public, structured content failures."""


class ContentError(ValueError):
    def __init__(self, message: str, *, source: str = "<memory>", path: str = "$", code: str = "invalid_content"):
        self.source = source
        self.path = path
        self.code = code
        self.message = message
        super().__init__(f"{source}:{path}: {code}: {message}")

    def __str__(self):
        return f"{self.source}:{self.path}: {self.code}: {self.message}"


class ContentIOError(ContentError):
    """Reading or atomically writing content failed."""


class UnknownContentReference(ContentError):
    def __init__(self, section: str, id: str, *, source: str = "<memory>", path: str = "$"):
        self.section = section
        self.id = id
        super().__init__(f"Unknown reference {section}:{id}", source=source, path=path, code="unknown_reference")


class ContextBudgetExceeded(ContentError):
    def __init__(self, actual_chars: int, max_chars: int):
        self.actual_chars = actual_chars
        self.max_chars = max_chars
        super().__init__(f"Context has {actual_chars} characters; limit is {max_chars}", code="context_budget_exceeded")
