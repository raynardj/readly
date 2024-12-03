import os


def get_secret(key):
    secret = os.getenv(key)
    if secret is None:
        from glow.secrets import GLOW_SECRETS

        secret = GLOW_SECRETS[key]
    return secret


DEEPGRAM_API_KEY = get_secret("READLY_DEEPGRAM_API_KEY")

SPEAK_URL = "https://api.deepgram.com/v1/speak"

GOOGLE_CLIENT_ID = "220458966244-loo7pj7q2dibu4u0fbgps6qm8466idom.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = get_secret("GOOGLE_CLIENT_SECRET")
READLY_SECRET_KEY = get_secret("READLY_SECRET_KEY")

REDIS_HOST = "localhost"
REDIS_PORT = 6379
