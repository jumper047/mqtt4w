from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from pydantic import BaseModel

from mqtt4w.services.common.discovery import UNIQUE_ID
from mqtt4w.services.dpms import ServiceModel as DPMSModel
from mqtt4w.services.file_usage_tracker import ServiceModel as FileUsageModel
from mqtt4w.services.windows_tracker import ServiceModel as WindowTrackerModel


class ServicesModel(BaseModel):
    windows_tracker: WindowTrackerModel = WindowTrackerModel()
    file_usage: FileUsageModel = FileUsageModel()
    dpms: DPMSModel = DPMSModel()

    def list(self):
        # return [self.windows_tracker, self.file_usage, self.dpms]
        return [self.dpms, self.file_usage]


class MqttModel(BaseModel):
    hostname: str
    port: int = 1883
    username: str
    password: str


class LoggingModel(BaseModel):
    level: str = "INFO"
    # Should uncomment when bumping min python to 3.8
    # level: Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"] = "INFO"
    filename: Optional[Path] = None


class BaseConfig(BaseModel):
    workstation_name: str = "workstation"
    workstation_id: str = UNIQUE_ID
    base_topic: Path = Path("mqtt4w")
    discovery_enabled: bool = True
    discovery_prefix: Path = Path("homeassistant")
    availability_subtopic: Path = Path("available")


class Config(BaseModel):
    base: BaseConfig = BaseConfig()
    mqtt: MqttModel
    logging: LoggingModel = LoggingModel()
    services: ServicesModel = ServicesModel()


def load_config(config_path: str) -> Config:
    with open(config_path, encoding="utf-8") as c:
        config_dict = yaml.safe_load(c)
    return Config(**config_dict)
