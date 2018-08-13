from sanic import response, Sanic

from functools import wraps

import aiohttp

import json
import os

app = Sanic(__name__)

with open('data/status_codes.json') as f:
    app.status_codes = json.load(f)


def authorized():
    def decorator(f):
        @wraps(f)
        async def decorated_function(request, *args, **kwargs):
            if request.token == 'hunter2':
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
# @authorized()
async def index(request):
    return response.json({'hello': 'world'})


@app.route('/status/<status>')
async def status_code(request, status):
    try:
        info = app.status_codes[status]
    except KeyError:
        return response.json({'error': True, 'status': status, 'message': 'invalid status'})
    else:
        return response.json({'error': False, 'status': status, 'info': info})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.getenv('PORT') or 5000)
