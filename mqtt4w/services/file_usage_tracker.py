import subprocess
import shutil
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import asyncio
from asyncinotify import Inotify, Mask
from mqtt4w.helpers import make_topic
from mqtt4w.services.common import Service, ServiceBaseModel
from pydantic import BaseModel


@dataclass
class Sensor:
    entities: Dict[str, bool] = field(default_factory=dict)
    task: Optional[asyncio.Task] = None

    @property
    def enabled(self):
        return any(self.entities.values())


class FileUsageService(Service):
    """Exposes information about any file opened.

    This service is mostly usefull to track usage of the camera/microphone,
    but can be used in any other scenario."""

    # https://unix.stackexchange.com/questions/79483/can-i-query-which-processes-if-any-are-currently-accessing-the-microphone
    # https://unix.stackexchange.com/questions/344454/how-to-know-if-my-webcam-is-used-or-not
    # https://asyncinotify.readthedocs.io/en/latest/

    def __init__(self, client, base_topic, *, subtopic, sensors):
        sensors = sensors or {}
        self.client = client
        self.topic = base_topic / subtopic
        self.sensors = self.get_sensors_struct(sensors)
        self.tracked_files = self.get_tracked_files(sensors)
        self.fuser_available = shutil.which("fuser")

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

    async def advertise(self):
        for sensor in self.sensors:
            config_topic = self.topic / sensor / "config"
            state_topic = self.topic / sensor / "state"
            config = {"name": sensor, "state_topic": state_topic}
            payload = json.dumps(config)
            await self.publish(config_topic, payload, qos=1, retain=True)

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
        await self.publish_binary_states(states)
        async for event in inotify:
            sensor = self.tracked_files[str(event.path)]
            self.sensors[sensor].entities[event.path] = event.mask == Mask.OPEN
            new_states = self.get_states()
            states_changed = {s: st for s, st in new_states.items() if st != states[s]}
            if states_changed:
                for s in states_changed:
                    sensor = self.sensors[s]
                    if sensor.task:
                        sensor.task.cancel()
                    state_topic = self.topic / s / "state"
                    payload = 'ON' if states_changed[s] else 'OFF'
                    sensor.task = asyncio.create_task(self.publish_with_delay(state_topic, payload, 1))
                states = new_states


    async def publish_with_delay(self, topic, payload, delay):
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            pass
        else:
            await self.publish(topic, payload, qos=1)
                
    async def process_message(self, _):
        return None


class ServiceModel(ServiceBaseModel):
    _constructor = FileUsageService
    subtopic: str = "file_usage_tracker"
    sensors: Optional[Dict[str, List[str]]] = None
                
