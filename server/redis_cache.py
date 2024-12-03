from constants import REDIS_HOST, REDIS_PORT

import redis
import json


redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)


def set_auth_user(token: str, user: dict, oauth_type: str = "google"):
    redis_client.set(f"{oauth_type}:{token[:20]}", json.dumps(user))


def get_auth_user(token: str, oauth_type: str = "google"):
    res = redis_client.get(f"{oauth_type}:{token[:20]}")
    if res is not None:
        return json.loads(res)
    return None
