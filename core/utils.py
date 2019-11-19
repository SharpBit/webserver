from sanic import response

from dotenv import load_dotenv, find_dotenv
from jinja2 import Environment, PackageLoader
from functools import wraps
from contextlib import asynccontextmanager

import asyncpg


load_dotenv(find_dotenv('.env'))


class Oauth2:
    def __init__(self, client_id, client_secret, scope=None, redirect_uri=None, session=None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self.redirect_uri = redirect_uri
        self.discord_login_url = 'https://discordapp.com/api/oauth2/authorize?client_id={}&redirect_uri={}&response_type=code&scope={}'.format(client_id, redirect_uri, scope)
        self.discord_token_url = 'https://discordapp.com/api/oauth2/token'
        self.discord_api_url = 'https://discordapp.com/api/v6'
        self.session = session

    async def get_access_token(self, code):
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

    async def get_user_json(self, access_token):
        url = self.discord_api_url + '/users/@me'

        headers = {
            'Authorization': 'Bearer {}'.format(access_token)
        }

        async with self.session.get(url, headers=headers) as z:
            resp = await z.json()
        return resp


@asynccontextmanager
async def open_db_connection(app, **options):
    user = options.pop('user', app.config.DB_USERNAME)
    password = options.pop('password', app.config.DB_PASSWORD)
    database = options.pop('database', app.config.DB_NAME)
    host = options.pop('host', app.config.DB_HOST)

    # try:
    conn = await asyncpg.connect(user=user, password=password, database=database, host=host)
    yield conn
    # finally:
    await conn.close()

async def render_template(template, request, **kwargs):
    env = Environment(loader=PackageLoader('core', 'templates'))
    template = env.get_template(template)
    kwargs['logged_in'] = request['session'].get('logged_in', False)

    if kwargs['logged_in']:
        async with open_db_connection(request.app) as conn:
            user = await conn.fetchrow('SELECT * FROM users WHERE id = $1', request['session']['id'])
        kwargs['avatar'] = user['avatar']
        kwargs['username'] = user['name']
        kwargs['discrim'] = user['discrim']

    html_content = template.render(**kwargs)
    return response.html(html_content)

def login_required():
    def decorator(func):
        @wraps(func)
        async def wrapper(request, *args, **kwargs):
            if not request['session'].get('logged_in'):
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

def base36encode(number):
    if not isinstance(number, int):
        raise TypeError('number must be an integer')
    if number < 0:
        raise ValueError('number must be positive')

    alphabet, base36 = ['0123456789abcdefghijklmnopqrstuvwxyz', '']

    while number:
        number, i = divmod(number, 36)
        base36 = alphabet[i] + base36

    return base36 or alphabet[0]
