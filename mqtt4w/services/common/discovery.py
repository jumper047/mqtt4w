import json
import pathlib
import uuid
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Dict

from mqtt4w import VERSION
from mqtt4w.services.common.constants import OFF, OFFLINE, ON, ONLINE
from mqtt4w.services.common.structures import Message

UNIQUE_ID = str(uuid.getnode())

BUTTON_PAYLOAD = {
    "pl_on": ON,
    "pl_off": OFF,
}
AVAILABILITY_PAYLOAD = {
    "pl_avail": ONLINE,
    "pl_not_avail": OFFLINE,
}
SUBTOPIC_TEMPLATE = "{type}/{id}/config"


class EntityType(Enum):
    BUTTON = "button"
    BINARY_SENSOR = "binary_sensor"


@dataclass
class DiscoveryEntity:
    type: EntityType
    id: str
    subconfig: Dict[str, Any]


def generate_device_cfg(name, id):
    return {
        "device": {
            "name": name,
            "manufacturer": "Jumper Heavy Industries",
            "model": "MQTT4Workstations",
            "sw_version": VERSION,
            "identifiers": [id],
        }
    }


def generate_availability_config(availability_topic):
    return {"availability_topic": str(availability_topic), **AVAILABILITY_PAYLOAD}


def generate_subconfig(
    name,
    icon=None,
    command_topic=None,
    state_topic=None,
    payload_on=None,
    payload_off=None,
    payload_press=None,
):
    subconfig = {"name": name}
    if icon:
        subconfig["icon"] = icon
    if command_topic:
        subconfig["command_topic"] = command_topic
    if state_topic:
        subconfig["state_topic"] = state_topic
    if payload_on:
        subconfig["payload_on"] = payload_on
    if payload_off:
        subconfig["payload_off"] = payload_off
    if payload_press:
        subconfig["payload_press"] = payload_press
    return subconfig


def generate_binary_sensor_config():
    pass


def generate_sensor_config():
    pass


def expand_discovery_entity(
    entity: DiscoveryEntity,
    uniq_id,
    base_topic: pathlib.Path,
    workstation_name: str,
    availability_topic: pathlib.Path,
) -> Message:
    subconfig = entity.subconfig
    topic_keys = ["command_topic", "state_topic"]
    for k in topic_keys:
        if k in subconfig:
            subconfig[k] = str(base_topic / subconfig[k])
    expanded_id = "_".join([uniq_id, entity.id])
    config = {
        "uniq_id": expanded_id,
        **subconfig,
        **generate_device_cfg(workstation_name, uniq_id),
        **generate_availability_config(availability_topic),
    }
    topic = SUBTOPIC_TEMPLATE.format(type=entity.type.value, id=expanded_id)
    return Message(topic, json.dumps(config), discovery=True)
