from aiohttp import ClientSession
from contextlib import asynccontextmanager
from functools import wraps

import asyncpg
from jinja2 import Environment, PackageLoader
from sanic import response, Sanic
from sanic.request import Request
from sanic.response import HTTPResponse


class Oauth2:
    """An Oauth2 class to handle logging in with Discord"""

    def __init__(self, client_id: str, client_secret: str, scope: str, redirect_uri: str, session: ClientSession):
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self.redirect_uri = redirect_uri
        self.discord_login_url = 'https://discord.com/api/oauth2/authorize' + \
            f'?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&scope={scope}'
        self.discord_token_url = 'https://discord.com/api/oauth2/token'
        self.discord_api_url = 'https://discord.com/api/v6'
        self.session = session

    async def get_access_token(self, code: str):
        """Get an access token to make a request to the Discord API

        Parameters
        ----------
        code: str
            The code that gets sent to the request arguments when the user is redirected
            back to the redirect URI after authorization.
        """
        payload = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': self.redirect_uri,
            'scope': self.scope
        }

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        async with self.session.post(self.discord_token_url, data=payload, headers=headers) as z:
            resp = await z.json()
        return resp.get('access_token')

    async def get_user_json(self, access_token: str):
        """Get user information with our new access token"""
        url = self.discord_api_url + '/users/@me'

        headers = {
            'Authorization': f'Bearer {access_token}'
        }

        async with self.session.get(url, headers=headers) as z:
            resp = await z.json()
        return resp


@asynccontextmanager
async def open_db_connection(app: Sanic, **options):
    user = options.pop('user', app.config.DB_USERNAME)
    password = options.pop('password', app.config.DB_PASSWORD)
    database = options.pop('database', app.config.DB_NAME)
    host = options.pop('host', app.config.DB_HOST)

    # try:
    conn = await asyncpg.connect(user=user, password=password, database=database, host=host)
    yield conn
    # finally:
    await conn.close()

async def render_template(template: str, request: Request, **context) -> HTTPResponse:
    """
    Function to return jinja variables to the html
    """
    env = Environment(loader=PackageLoader('core', 'templates'))
    template = env.get_template(template + '.html')
    context['logged_in'] = request.ctx.session['logged_in']

    if context['logged_in']:
        async with open_db_connection(request.app) as conn:
            user = await conn.fetchrow('SELECT * FROM users WHERE id = $1', request.ctx.session['id'])
        context['avatar'] = user['avatar']
        context['username'] = user['name']
    context['messages'] = request.ctx.session['messages']

    html_content = template.render(**context)
    request.ctx.session['messages'] = []  # Clear messages after every request
    return response.html(html_content)

def add_message(request: Request, category: str, message: str, redirect_to: str):
    """Add a flash message to appear at the top of a page and redirect to an endpoint"""
    request.ctx.session['messages'].append([category, message])
    return response.redirect(redirect_to)


def disable_xss(content: str) -> str:
    """Prevent cross-site scripting"""
    return content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def login_required():
    def decorator(func):
        @wraps(func)
        async def wrapper(request, *args, **kwargs):
            if not request.ctx.session['logged_in']:
                return response.redirect('/login')
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator

def authorized():
    def decorator(f):
        @wraps(f)
        async def decorated_function(request, *args, **kwargs):
            if request.token == request.app.config.REQUEST_TOKEN:
                return await f(request, *args, **kwargs)
            return response.json({'error': True, 'message': 'Unauthorized'}, status=401)
        return decorated_function
    return decorator
