"""Base service module."""


class BaseService:
    """Base class for application services."""

    def __init__(self, service_name: str):
        self.service_name = service_name

    def get_status(self) -> str:
        return f"Service {self.service_name} is active"
