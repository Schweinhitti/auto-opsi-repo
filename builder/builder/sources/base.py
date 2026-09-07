from typing import Protocol

from ..models import Release


class Source(Protocol):
    def resolve(self, package: dict) -> Release: ...
