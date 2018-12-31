from sanic import response, Sanic

from functools import wraps

import aiohttp

import json
import os

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


@app.listener('after_server_stop')
async def close_session(app, loop):
    await app.session.close()


@app.route('/')
async def index(request):
    return response.json({'hello': 'world'})


if __name__ == '__main__':
    app.run(port=4000)
