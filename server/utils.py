import asyncio
import spacy
from traceback import format_exc

from logger import logger
from authlib.integrations.starlette_client import OAuth

from constants import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET


def await_coroutine(coroutine):
    """
    Helper function to await a coroutine in a synchronous context
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(coroutine)
        return result
    except Exception as e:
        logger.error(f"🔌 Traceback: {format_exc()}")
        logger.error(f"Error in await_coroutine: {str(e)}")
        return None


# load only sentence tokenizer
sentence_tokenizer = spacy.load("en_core_web_sm", disable=["ner", "parser"])
sentence_tokenizer.add_pipe("sentencizer")


oauth = OAuth()
oauth.register(
    name="google",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)
