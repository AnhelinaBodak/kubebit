from models import Challenge


def get_container_data(challenge_id: int):
    challenge = Challenge.query.get(challenge_id)
    if not challenge:
        raise ValueError("Challenge not found")

    config = challenge.container_challenge
    if not config:
        raise ValueError("Container config missing")

    return config