import shutil
import subprocess
from asyncio import Queue
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncGenerator, Dict, List

from asyncinotify import Inotify, Mask
from mqtt4w.services.common import (
    Message,
    ServiceBaseModel,
    messages_for_states_generator,
)
from mqtt4w.services.common.baseservice import BaseService
from mqtt4w.services.common.constants import OFF, ON
from mqtt4w.services.common.discovery import (
    DiscoveryEntity,
    EntityType,
    generate_subconfig,
)
from pydantic import Field


@dataclass
class Sensor:
    entities: Dict[str, bool] = field(default_factory=dict)

    @property
    def enabled(self):
        return any(self.entities.values())


class FileUsageService(BaseService):
    """Exposes information about any file opened.

    This service is mostly usefull to track usage of the camera/microphone,
    but can be used in any other scenario."""

    # https://unix.stackexchange.com/questions/79483/can-i-query-which-processes-if-any-are-currently-accessing-the-microphone
    # https://unix.stackexchange.com/questions/344454/how-to-know-if-my-webcam-is-used-or-not
    # https://asyncinotify.readthedocs.io/en/latest/

    def __init__(self, *, subtopic, sensors):
        super().__init__()
        sensors = sensors or {}
        self.subtopic = subtopic
        self.sensors = self.get_sensors_struct(sensors)
        self.tracked_files = self.get_tracked_files(sensors)
        self.fuser_available = shutil.which("fuser")
        self.register_discoverables()

    def register_discoverables(self):

        for sensor in self.sensors:
            subconfig = generate_subconfig(
                name=sensor,
                state_topic=self.subtopic / sensor / "state",
                payload_on=ON,
                payload_off=OFF,
            )
            sensor_id = sensor
            self.register_discoverable(EntityType.BINARY_SENSOR, sensor_id, subconfig)

    def get_sensors_struct(self, sensors):
        s = {x: Sensor() for x in sensors}
        for sensor, files in sensors.items():
            for file in files:
                s[sensor].entities[file] = False
        return s

    def get_tracked_files(self, sensors):
        tracked_files = {}
        for sensor_name, files in sensors.items():
            for file in files:
                tracked_files[file] = sensor_name
        return tracked_files

    def discovery(self) -> List[DiscoveryEntity]:
        messages = []
        # return messages

        for sensor in self.sensors:
            subconfig = generate_subconfig(
                name=sensor,
                state_topic=self.subtopic / sensor / "state",
                payload_on=ON,
                payload_off=OFF,
            )
            sensor_id = sensor
            messages.append(
                DiscoveryEntity(EntityType.BINARY_SENSOR, sensor_id, subconfig)
            )
        return messages

    def already_opened(self, device):
        p = subprocess.run(["fuser", device], capture_output=True)
        return bool(p.stdout)

    def set_initial_states(self):
        for file, sensor in self.tracked_files.items():
            if self.already_opened(file):
                self.sensors[sensor].entities[file] = True

    def get_states(self):
        states = {}
        for sensor in self.sensors:
            states[sensor] = self.sensors[sensor].enabled
        return states

    async def start(self):
        inotify = Inotify()
        for f in self.tracked_files:
            inotify.add_watch(f, Mask.OPEN | Mask.CLOSE)
        self.set_initial_states()
        states = self.get_states()
        async for message in messages_for_states_generator(states, self.subtopic):
            yield message
        async for event in inotify:
            sensor = self.tracked_files[str(event.path)]
            self.sensors[sensor].entities[event.path] = event.mask == Mask.OPEN
            new_states = self.get_states()
            states_changed = {s: st for s, st in new_states.items() if st != states[s]}
            if states_changed:
                for s in states_changed:
                    sensor = self.sensors[s]
                    state_topic = self.subtopic / s / "state"
                    payload = ON if states_changed[s] else OFF
                    yield Message(str(state_topic), payload)
                states = new_states


class ServiceModel(ServiceBaseModel):
    _constructor = FileUsageService

    subtopic: Path = Path("file_usage_tracker")
    sensors: Dict[str, List[str]] = Field(default_factory=dict)
