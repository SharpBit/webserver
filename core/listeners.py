import aiohttp
import brawlstats

from core.config import Config
from core.utils import Oauth2
from sanic import Blueprint

listeners = Blueprint('listeners')

@listeners.listener('before_server_start')
async def init(app, loop):
    app.session = aiohttp.ClientSession(loop=loop)
    app.brawl_client = brawlstats.Client(
        token=Config.BRAWLSTATS_TOKEN,
        session=app.session,
        is_async=True
    )
    app.oauth = Oauth2(
        Config.DISCORD_CLIENT_ID,
        Config.DISCORD_CLIENT_SECRET,
        scope='identify',
        redirect_uri='https://sharpbit.tk/callback' if not Config.DEV else 'http://127.0.0.1:4000/callback',
        session=app.session
    )

@listeners.listener('after_server_stop')
async def close_session(app, loop):
    await app.session.close()
