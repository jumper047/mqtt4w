import asyncio
import json
from collections import defaultdict
from typing import Dict, List, Optional

import Xlib
from ewmh import EWMH
from mqtt4w.helpers import make_topic
from mqtt4w.services.common import Service, ServiceBaseModel
from pydantic import BaseModel


class WindowsTrackerService(Service):
    """Exposes information about specified windows

    Tracker topic contains subtopics which tracking
    certain windows. For example if you set up
    tracking of thhe viber call window
    windows_tracker/viber/state
    will switch to ON if window exists and OFF otherwise.
    ... but more features to come"""

    def __init__(
            self,
            client,
            base_topic,
            *,
            subtopic,
            expose_active_window, 
            sensors
    ):
        sensors = sensors or {}
        self.topic = base_topic / subtopic
        self.ewmh = self.create_ewmh()
        self.client = client
        self.expose_active_window = expose_active_window
        self.sensors = list(sensors.keys())
        self.tracked_titles = self.get_tracked_titles(sensors)

    def create_ewmh(self):
        e = EWMH()
        root = e.display.screen().root
        root.change_attributes(event_mask=Xlib.X.SubstructureNotifyMask)
        return e

    def get_tracked_titles(self, sensors):
        tracked_titles = defaultdict(lambda: [])
        for sensor_name, titles in sensors.items():
            for title in titles:
                tracked_titles[title].append(sensor_name)
        return tracked_titles
            
    async def advertise(self, prefix, node_id):
        for sensor in self.sensors:
            config_topic = prefix / "binary_sensor" / node_id / "config"
            state_topic = self.topic / sensor / 'state'
            config = {
                'name': sensor,
                'state_topic': state_topic
            }
            payload = json.dumps(config)
            await self.publish(config_topic, payload, qos=1, retain=True)

    def all_windows_titles(self):
        titles = set()
        client_list = self.ewmh.getClientList()
        for window in client_list:
            try:
                window_title = self.ewmh.getWmName(window).decode()
            except Xlib.error.BadWindow:
                continue
            else:
                titles.add(window_title)
        return titles

    def sensors_states(self):
        states = {x: False for x in self.sensors}
        for title in self.all_windows_titles():
            if title in self.tracked_titles:
                for sensor in self.tracked_titles[title]:
                    states[sensor] = True
        return states

    async def start(self):
        states = self.sensors_states()
        await self.publish_binary_states(states)
        loop = asyncio.get_running_loop()
        while True:
            # await asyncio.to_thread(self.ewmh.display.next_event)
            await loop.run_in_executor(None, self.ewmh.display.next_event)
            new_states = self.sensors_states()
            changed = {t: v for t, v in new_states.items() if v != states[t]}
            if changed:
                await self.publish_binary_states(changed)
            states = new_states

    async def process_message(self, _):
        return None


class ServiceModel(ServiceBaseModel):
    _constructor = WindowsTrackerService

    subtopic: str = "windows_tracker"
    expose_active_window: bool = True
    sensors: Optional[Dict[str, List[str]]] = None
            
