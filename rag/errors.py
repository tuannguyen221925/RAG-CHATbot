class RAGError(Exception):
    """Lỗi nghiệp vụ có thể hiển thị trực tiếp cho người dùng."""


class InvalidInput(RAGError):
    pass


class TopicNotFound(RAGError):
    pass


class Conflict(RAGError):
    pass


class ConfigurationError(RAGError):
    pass
