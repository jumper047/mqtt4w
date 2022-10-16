from typing import Callable, Optional

from pydantic import BaseModel

from .abc import AbstractService


class ServiceConfigError(Exception):
    pass


class ServiceBaseModel(BaseModel):
    _constructor: Optional[Callable] = None

    def create_instance(self) -> AbstractService:
        if self._constructor:
            return self._constructor(**self.dict())
        else:
            raise ServiceConfigError
