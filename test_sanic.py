from sanic import response, Sanic

from functools import wraps

import aiohttp

app = Sanic(__name__)


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
async def index(request):
    return response.json({'hello': 'world'})


@app.route('/test')
async def test(request):
    async with app.session.get('https://leaderboard.brawlstars.com') as resp:
        data = await resp.text()
    return response.text(data)


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000)
