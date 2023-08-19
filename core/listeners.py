import aiohttp

from core.utils import Oauth2
from sanic import Blueprint, Sanic

listeners = Blueprint('listeners')

@listeners.listener('before_server_start')
async def init(app: Sanic, loop):
    app.ctx.aiohttp = aiohttp.ClientSession(loop=loop)
    print(app.config.DISCORD_CLIENT_ID)
    print(app.config.DISCORD_CLIENT_SECRET)
    app.ctx.oauth = Oauth2(
        client_id=app.config.DISCORD_CLIENT_ID,
        client_secret=app.config.DISCORD_CLIENT_SECRET,
        scope='identify',
        redirect_uri=f"http{'s' if not app.config.DEV else ''}://{app.config.DOMAIN}/callback",
        session=app.ctx.aiohttp
    )

@listeners.listener('after_server_stop')
async def close_session(app: Sanic, loop):
    await app.ctx.aiohttp.close()
