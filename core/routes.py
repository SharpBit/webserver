import asyncio
import random
import string

from sanic import Blueprint, response

from core.utils import login_required, open_db_connection, render_template

root = Blueprint('root')

@root.get('/')
async def index(request):
    async with request.app.session.get('https://api.github.com/users/SharpBit/events/public') as resp:
        info = await resp.json()
    recent_commits = filter(lambda x: x['repo']['name'] != 'SharpBit/modmail' and x['type'] == 'PushEvent', info)
    return await render_template('index.html', request, title="Home Page", description='Home Page', recent=recent_commits)

@root.get('/invite')
async def invite(request):
    return response.redirect('https://discord.gg/C2tnmHa')

@root.get('/repo/<name>')
async def repo(request, name):
    return response.redirect(f'https://github.com/SharpBit/{name}')


@root.get('/login')
async def login(request):
    if request['session'].get('logged_in'):
        return response.redirect('/')
    return response.redirect(request.app.oauth.discord_login_url)

@root.get('/callback')
async def callback(request):
    app = request.app
    code = request.raw_args.get('code')
    access_token = await app.oauth.get_access_token(code)
    user = await app.oauth.get_user_json(access_token)
    if user.get('message'):
        return await render_template('unauthorized.html', request, description='Discord Oauth Unauthorized.')

    if user.get('avatar'):
        avatar = 'https://cdn.discordapp.com/avatars/{}/{}.png'.format(user['id'], user['avatar'])
    else: # in case of default avatar users
        avatar = 'https://cdn.discordapp.com/embed/avatars/{}.png'.format(user['discriminator'] % 5)

    async with open_db_connection(request.app) as conn:
        await conn.executemany(
            '''INSERT INTO users(id, name, discrim, avatar) VALUES ($1, $2, $3, $4)
            ON CONFLICT (id) DO UPDATE SET id=$1, name=$2, discrim=$3, avatar=$4''',
            [(user['id'], user['username'], user['discriminator'], avatar), (user['id'], user['username'], user['discriminator'], avatar)]
        )

    resp = response.redirect('/dashboard')

    request['session']['logged_in'] = True
    request['session']['id'] = user['id']

    return resp

@root.get('/logout')
async def logout(request):
    del request['session']['logged_in']
    del request['session']['id']
    return response.redirect('/')

@root.get('/dashboard')
@login_required()
async def dashboard_home(request):
    async with open_db_connection(request.app) as conn:
        urls = await conn.fetch('SELECT * FROM urls WHERE user_id = $1', request['session']['id'])
        pastes = await conn.fetch('SELECT * FROM pastebin WHERE user_id = $1', request['session']['id'])
    return await render_template(
        'dashboard.html',
        request,
        title="Dashboard",
        description='Dashboard for your account.',
        urls=urls,
        pastes=pastes
    )

@root.get('/urlshortener')
async def url_shortener_home(request):
    return await render_template('url_shortener.html', request, title="URL Shortener", description='Shorten a URL!')

@root.post('/url/create')
# @authorized()
async def create_url(request):
    chars = string.ascii_letters + string.digits
    code = ''.join(random.choice(chars) for i in range(8))
    url = request.form['url'][0]
    account = request['session'].get('id', 'no_account')

    async with open_db_connection(request.app) as conn:
        if request.form.get('code'):
            code = request.form['code'][0]
            existing = await conn.fetchrow('SELECT * FROM urls WHERE code = $1', code)
            if existing:
                return response.text('Error: Code already exists')
        await conn.execute('INSERT INTO urls(user_id, code, url) VALUES ($1, $2, $3)', account, code, url)
    return response.text(f'Here is your shortened URL: https://sharpbit.tk/{code}')

@root.get('/<code>')
async def existing_code(request, code):
    async with open_db_connection(request.app) as conn:
        res = await conn.fetchrow('SELECT * FROM urls WHERE code = $1', code)
    if not res:
        return response.text(f'No such URL shortener code "{code}" found.')
    return response.redirect(res['url'])

@root.get('/pastebin')
async def pastebin_home(request):
    return await render_template('pastebin.html', request, title="Pastebin", description='Paste in code for easy access later!')

@root.post('/pastebin/create')
# @authorized()
async def create_pastebin(request):
    chars = string.ascii_letters + string.digits
    code = ''.join(random.choice(chars) for i in range(8))
    text = request.form['text'][0]
    account = request['session'].get('id', 'no_account')
    async with open_db_connection(request.app) as conn:
        await conn.execute('INSERT INTO pastebin(user_id, code, text) VALUES ($1, $2, $3)', account, code, text)
    return response.redirect(f'{request.app.config.DOMAIN}/{code}')

@root.get('/pastebin/<code>')
async def existing_pastebin(request, code):
    async with open_db_connection(request.app) as conn:
        res = await conn.fetchrow('SELECT * FROM pastebin WHERE code = $1', code)
    if not res:
        return response.text(f'No such pastebin code "{code}" found.')
    text = res['text'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return await render_template('saved_pastebin.html', request, title="Pastebin - Saved", description="Saved Pastebin", code=text)

@root.get('/brawlstats/<endpoint>')
async def brawlstats_tests_proxy(request, endpoint):
    app = request.app
    headers = {
        'Authorization': 'Bearer {}'.format(app.config.BRAWLSTATS_OFFICIAL_TOKEN),
        'Accept-Encoding': 'gzip'
    }
    try:
        async with app.session.get(f'https://api.brawlstars.com/v1/{endpoint}', timeout=30, headers=headers) as resp:
            return response.json(await resp.json(), status=resp.status)
    except asyncio.TimeoutError:
        return response.text("Request failed", status=503)
