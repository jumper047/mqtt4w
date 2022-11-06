from typing import Callable, Optional

from mqtt4w.services.common.baseservice import BaseService
from pydantic import BaseModel


class ServiceConfigError(Exception):
    pass


class ServiceBaseModel(BaseModel):
    _constructor: Optional[Callable] = None

    def create_instance(self, *args) -> BaseService:
        if self._constructor:
            return self._constructor(*args, **self.dict())
        else:
            raise ServiceConfigError
