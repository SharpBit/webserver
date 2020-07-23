import aiohttp
import brawlstats

from core.utils import Oauth2
from sanic import Blueprint

listeners = Blueprint('listeners')

@listeners.listener('before_server_start')
async def init(app, loop):
    app.session = aiohttp.ClientSession(loop=loop)
    app.brawl_client = brawlstats.Client(
        token=app.config.BRAWLSTATS_TOKEN,
        session=app.session,
        is_async=True
    )
    app.oauth = Oauth2(
        app.config.DISCORD_CLIENT_ID,
        app.config.DISCORD_CLIENT_SECRET,
        scope='identify',
        redirect_uri=f'https://{app.config.DOMAIN}/callback',
        session=app.session
    )

@listeners.listener('after_server_stop')
async def close_session(app, loop):
    await app.session.close()
