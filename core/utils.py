from sanic import response

from dotenv import load_dotenv, find_dotenv
from jinja2 import Environment, PackageLoader
from functools import wraps
from contextlib import asynccontextmanager

import asyncpg
import os


load_dotenv(find_dotenv('.env'))

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

def authorized():
    def decorator(f):
        @wraps(f)
        async def decorated_function(request, *args, **kwargs):
            if request.token == os.getenv('AUTH'):
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
