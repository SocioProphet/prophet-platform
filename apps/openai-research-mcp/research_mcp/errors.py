class ResearchMcpError(Exception):
    def __init__(self, code: str, message: str, http_status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status

    def to_dict(self):
        return {"error": self.code, "message": self.message}


class InvalidInputError(ResearchMcpError):
    def __init__(self, message: str):
        super().__init__("invalid_input", message, 400)


class AuthError(ResearchMcpError):
    def __init__(self, message: str = "unauthorized"):
        super().__init__("unauthorized", message, 401)


class ForbiddenError(ResearchMcpError):
    def __init__(self, message: str = "forbidden"):
        super().__init__("forbidden", message, 403)


class DocumentNotFoundError(ResearchMcpError):
    def __init__(self, message: str = "document not found"):
        super().__init__("document_not_found", message, 404)


class BackendUnavailableError(ResearchMcpError):
    def __init__(self, message: str = "backend unavailable"):
        super().__init__("backend_unavailable", message, 502)


class BackendProtocolError(ResearchMcpError):
    def __init__(self, message: str = "backend protocol error"):
        super().__init__("backend_protocol_error", message, 502)
