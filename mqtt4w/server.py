async def listen_messages(client, root_topic, handlers):
    async with client.unfiltered_messages() as messages:
        await client.subscribe(f'{root_topic}/')
        async for message in messages:
            asyncio.gather(handler(message) for handler in handlers)
            # for handler in handlers:
            #     await 
            # # message.payload.decode()
            # # message.topic
            # pass
