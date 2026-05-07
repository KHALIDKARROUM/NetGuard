<<<<<<< HEAD
"""exceptions.py — Exceptions personnalisées du backend."""
=======
"""exceptions.py — Exceptions personnalisées."""
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736


class DataLoadError(Exception):
    def __init__(self, message: str, details: str = ""):
        self.message = message
        self.details = details
        super().__init__(self.message)


class ModelError(Exception):
    def __init__(self, message: str, details: str = ""):
        self.message = message
        self.details = details
<<<<<<< HEAD
        super().__init__(self.message)


class APIError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
=======
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
        super().__init__(self.message)