from datetime import date, timedelta

from sanic import response

from jinja2 import Environment, PackageLoader
from functools import wraps
from contextlib import asynccontextmanager

import asyncpg


class Oauth2:
    def __init__(self, client_id, client_secret, scope=None, redirect_uri=None, session=None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self.redirect_uri = redirect_uri
        self.discord_login_url = 'https://discord.com/api/oauth2/authorize?client_id={}&redirect_uri={}&response_type=code&scope={}'.format(client_id, redirect_uri, scope)
        self.discord_token_url = 'https://discord.com/api/oauth2/token'
        self.discord_api_url = 'https://discord.com/api/v6'
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

async def render_template(template, request, **context):
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
        context['discrim'] = user['discrim']
    context['messages'] = request.ctx.session['messages']

    html_content = template.render(**context)
    request.ctx.session['messages'] = []  # Clear messages after every request
    return response.html(html_content)

def add_message(request, category, message, redirect_to=None):
    """Add a flash message to appear at the top of a page and redirect to an endpoint if provided"""
    request.ctx.session['messages'].append([category, message])
    if redirect_to:
        return response.redirect(redirect_to)


def disable_xss(content):
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


def daterange(start_date: date, end_date: date) -> list:
    '''Creates a list of dates from the start date to end date, inclusive'''
    day_count = (end_date - start_date).days + 1
    return [start_date + timedelta(days=i) for i in range(day_count)]



def thisweek(today: date) -> list:
    if 0 <= today.weekday() <= 4:
        # Monday to Friday
        monday = today - timedelta(days=today.weekday())  # Last Monday
    else:
        monday = today - timedelta(days=today.weekday() - 7)
    friday = monday + timedelta(days=4)

    return daterange(monday, friday)
