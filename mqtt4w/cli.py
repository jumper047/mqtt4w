import argparse
import asyncio
import logging
import sys
import os

from asyncio_mqtt import Client, MqttError
from xdg.BaseDirectory import save_config_path

from mqtt4w import NAME
from mqtt4w.config import load_config
from mqtt4w.manager import ServicesManager

LOG = logging.getLogger(__name__)


def parse_args():
    args_parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    args_parser.add_argument(
        "-c", "--config",
        default=os.path.join(save_config_path(NAME), "config.yaml"),
        help="Path to configuration file"
    )
    return args_parser.parse_args()
    

async def async_main():
    args = parse_args()
    config = load_config(args.config)
    logging.basicConfig(**config.logging.dict())
    LOG.info(f'Configuration file {args.config} loaded successfully')
    running = True
    while running:
        try:
            client = Client(**config.mqtt.client.dict())
            await client.connect()
            LOG.info('Connected to MQTT server')
            services = [cfg.create_instance() for cfg in config.services.list()]
            base_topic = config.mqtt.base_topic
            if config.workstation_name:
                base_topic /= config.workstation_name
            manager = ServicesManager(client, base_topic, services)
            await manager.start_all()
        except MqttError as error:
            LOG.error(f'Error: {error}')
            logging.info('Waiting and reconnecting')
            await asyncio.sleep(60)

def main():
    sys.exit(asyncio.run(async_main()))
