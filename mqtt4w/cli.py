import argparse
import asyncio
import logging
import sys
import os

from asyncio_mqtt import Client, MqttError
from xdg.BaseDirectory import save_config_path

from mqtt4w import NAME
from mqtt4w.config import load_config


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


async def listen_messages(client, root_topic, handlers):
    async with client.unfiltered_messages() as messages:
        await client.subscribe(f'{root_topic}/')
        async for message in messages:
            asyncio.gather(handler(message) for handler in handlers)
            # # message.payload.decode()
            # # message.topic


    

async def async_main():
    args = parse_args()
    config = load_config(args.config)
    logging.getLogger().setLevel('INFO')
    logging.info(f'Configuration file {args.config} loaded')
    while True:
        try:
            client_conf = config.mqtt.client.dict()
            client = Client(**client_conf)
            await client.connect()
            services = []
            handlers = []
            tasks = set()
            topic = config.mqtt.base_topic / config.workstation_name
            for serv_conf in config.services.dict().values():
                constructor = serv_conf.pop('constructor')
                services.append(constructor(client, topic, **serv_conf))
            if config.mqtt.discovery.enabled:
                for service in services:
                    tasks.add(service.advertise(config.mqtt.discovery.prefix, config.workstation_name))
            for service in services:
                tasks.add(asyncio.create_task(service.start()))
                handlers.append(service.process_message)
            tasks.add(listen_messages(client, config.mqtt.base_topic, handlers))
            logging.info('Initializaion done, starting services.')
            await asyncio.gather(*tasks)
        except MqttError as error:
            logging.error(f'Error "{error}".')
            logging.info('Waiting and reconnecting')
            await asyncio.sleep(60)


def main():
    sys.exit(asyncio.run(async_main()))
