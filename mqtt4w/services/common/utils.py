from .structures import Message


async def messages_for_states_generator(states, topic):
    for name, state in states.items():
        state_topic = topic / name / "state"
        payload = "ON" if state else "OFF"
        yield Message(state_topic, payload)
