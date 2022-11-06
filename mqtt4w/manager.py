import asyncio
from pathlib import Path
from typing import AsyncGenerator, Callable, Coroutine, List, Optional

from asyncio_mqtt.client import Client

from mqtt4w.services.common import Message
from mqtt4w.services.common.baseservice import BaseService
from mqtt4w.services.common.constants import OFFLINE, ONLINE
from mqtt4w.services.common.discovery import expand_discovery_entity


class ServicesManager:
    def __init__(
        self,
        client: Client,
        services: List[BaseService],
        *,
        workstation_id: str,
        workstation_name: str,
        base_topic: Path,
        discovery_prefix: Path,
        discovery_enabled: bool,
        availability_subtopic: Path,
    ):
        self.running: bool = False
        self.mqtt_client = client
        self.base_topic = base_topic
        self.workstation_id = workstation_id
        self.workstation_name = workstation_name
        # TODO: normalize workstation name when using it as part of path!
        self.base_topic /= self.workstation_name
        self.discovery_prefix = discovery_prefix
        self.discovery_enabled = discovery_enabled
        self.availability_topic = base_topic / workstation_name / availability_subtopic
        self.tasks = set()
        for s in services:
            self.add_service(s)

    def add_service(self, service: BaseService) -> None:
        for initializer in service.initializers:
            self.tasks.add(initializer())
        for sender in service.senders:
            self.tasks.add(self._send_from(sender))
        # for receiver in service.receivers:
        #     if receiver
        # if service.incoming_msg:
        #     service_topic = self.base_topic / service.subtopic
        #     subscription_topic = service_topic / "#"
        #     self.tasks.add(self.mqtt_client.subscribe(str(subscription_topic)))
        #     messages = self.mqtt_client.filtered_messages(str(service_topic))
        #     self.tasks.add(
        #         self._receive_to(
        #             messages, str(subscription_topic), service.incoming_msg
        #         )
        #     )
        if self.discovery_enabled:
            self.tasks.add(self.advertise_service(service))

    async def advertise_service(self, service: BaseService):
        for entity in service.discoveries:
            message = expand_discovery_entity(
                entity,
                self.workstation_id,
                self.base_topic,
                self.workstation_name,
                self.availability_topic,
            )
            await self.send_message(message)

    async def send_message(self, message: Message):
        if message.discovery:
            topic = self.discovery_prefix / message.topic
        else:
            topic = self.base_topic / message.topic
        payload = message.payload
        await self.mqtt_client.publish(str(topic), payload, qos=1)

    async def start_all(self) -> None:
        self.running = True
        await self.mqtt_client.publish(str(self.availability_topic), ONLINE)
        await asyncio.gather(*self.tasks)
        await self.mqtt_client.publish(str(self.availability_topic), OFFLINE)

    async def _send_from(self, messages_get) -> None:
        async for message in messages_get():
            await self.send_message(message)

    async def _receive_to(self, messages, subtopic, incoming_queue):
        preamble = len(subtopic) + 1  # +1 for "/" in base/topic/subtopic
        async with messages as m:
            async for message in m:
                topic = message.topic[preamble:]
                parsed_message = Message(topic, message.payload.decode())
                await incoming_queue.put(parsed_message)
