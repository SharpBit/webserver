from sanic import Blueprint, response
from core.utils import render_template


home = Blueprint('main')

@home.get('/')
async def index(request):
    async with request.app.session.get('https://api.github.com/users/SharpBit/events/public') as resp:
        info = await resp.json()
    recent_commits = filter(lambda x: x['repo']['name'] != 'SharpBit/modmail' and x['type'] == 'PushEvent', info)
    return await render_template('index.html', request, title="Home Page", description='Home Page', recent=recent_commits)

@home.get('/invite')
async def invite(request):
    return response.redirect('https://discord.gg/C2tnmHa')

@home.get('/repo/<name>')
async def repo(request, name):
    return response.redirect(f'https://github.com/SharpBit/{name}')