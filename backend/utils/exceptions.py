"""exceptions.py — Exceptions personnalisées."""


class DataLoadError(Exception):
    def __init__(self, message: str, details: str = ""):
        self.message = message
        self.details = details
        super().__init__(self.message)


class ModelError(Exception):
    def __init__(self, message: str, details: str = ""):
        self.message = message
        self.details = details
        super().__init__(self.message)