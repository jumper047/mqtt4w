from pydantic import BaseModel
from abc import ABC, abstractmethod

class AbstractService(ABC):

    CONFIG_NAME: str
    SENSOR_TYPE: str

    @abstractmethod
    async def advertise(self):
        """This method advertises service via MQTT discovery."""

    @abstractmethod
    async def start(self):
        """Entry point for service."""

    @abstractmethod
    async def process_message(self, message):
        """Entry point for service."""


class Service(AbstractService):

    async def publish(self, topic, *args, **kwargs):
        return await self.client.publish(str(topic), *args, **kwargs)

    async def publish_binary_states(self, states):
        for name, state in states.items():
            state_topic = self.topic / name / "state"
            # state_topic = self.get_topic(name, "state")
            payload = 'ON' if state else 'OFF'
            await self.publish(state_topic, payload, qos=1)


class ServiceBaseModel(BaseModel):
    _constructor = None

    def dict(self, *args, **kwargs):
        d = super().dict(*args, **kwargs)
        d.update({'constructor': self._constructor})
        return d
