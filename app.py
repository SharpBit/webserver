from sanic import response, Sanic

from functools import wraps

import aiohttp
import time
import os

from dotenv import load_dotenv, find_dotenv
from motor.motor_asyncio import AsyncIOMotorClient


app = Sanic(__name__)


def authorized():
    def decorator(f):
        @wraps(f)
        async def decorated_function(request, *args, **kwargs):
            if request.token == os.environ.get('auth-token'):
                return await f(request, *args, **kwargs)
            return response.json({'error': True, 'message': 'Unauthorized'}, status=401)
        return decorated_function
    return decorator


@app.listener('before_server_start')
async def create_session(app, loop):
    app.session = aiohttp.ClientSession(loop=loop)
    load_dotenv(find_dotenv('.env'))
    app.config.MONGO = AsyncIOMotorClient(os.getenv('MONGO'), io_loop=loop).sharpbit.sharpbit


@app.listener('after_server_stop')
async def close_session(app, loop):
    await app.session.close()


@app.route('/')
async def index(request):
    return response.html(open('templates/index.html').read())

@app.route('/invite')
async def invite(request):
    return response.redirect('https://discord.gg/C2tnmHa')

@app.route('/repo/<name>')
async def repo(request, name):
    return response.redirect(f'https://github.com/SharpBit/{name}')

@app.route('/shorturl')
async def url_shortener(request):
    return response.html(open('templates/url_shortener.html').read())

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

@app.post('/ush')
async def ush(request):
    coll = request.app.config.MONGO.urls
    code = base36encode(int(time.time() * 1000))
    await coll.insert_one({'code': code, 'url': request.form['url'][0]})
    return response.text(f'Here is your shortened url: https://sharpbit.tk/{code}')

@app.route('/<code>')
async def short(request, code):
    coll = request.app.config.MONGO.urls
    res = await coll.find_one({'code': code})
    if not res:
        return response.text(f'No such URL shortener code "{code}" found.')
    return response.redirect(res['url'])


if __name__ == '__main__':
    app.run(port=4000)
