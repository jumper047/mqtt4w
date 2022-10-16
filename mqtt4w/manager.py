import asyncio
from pathlib import Path
from typing import AsyncGenerator, Callable, Coroutine, List, Optional

from asyncio_mqtt.client import Client

from mqtt4w.services.common import AbstractService, Message


class ServicesManager:
    def __init__(
        self, client: Client, base_topic: Path, services: List[AbstractService]
    ):
        self.mqtt_client = client
        self.base_topic = base_topic
        self.tasks = set()
        for s in services:
            self.add_service(s)

    async def _send_from(self, messages_gen) -> None:
        async for message in messages_gen:
            topic = self.base_topic / message.topic
            await self.mqtt_client.publish(str(topic), message.payload, qos=1)

    async def _receive_to(
        self, receiver_fn: Callable, subtopic: str, filter: Optional[str] = None
    ) -> None:
        topic = str(self.base_topic / subtopic)
        filter = filter or topic
        async with self.mqtt_client.filtered_messages(filter) as messages:
            await self.mqtt_client.subscribe(topic)
            async for message in messages:
                await receiver_fn(message.topic, message.payload.decode())

    def add_service(self, service: AbstractService) -> None:
        self.tasks.add(self._send_from(service.generate_message()))
        for receiver in service.message_receivers:
            self.tasks.add(
                self._receive_to(receiver.method, receiver.topic, receiver.filter)
            )

    async def start_all(self) -> None:
        await asyncio.gather(*self.tasks)
