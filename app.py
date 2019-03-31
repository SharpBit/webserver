import aiohttp
import inspect
import time

from jinja2 import Environment, PackageLoader
from sanic import response, Sanic
from sanic_session import Session
from motor.motor_asyncio import AsyncIOMotorClient

from core import config, login_required, Oauth


app = Sanic(__name__)
app.static('/static', './static')
app.static('/favicon.ico', './static/favicon.ico')

Session(app)
env = Environment(loader=PackageLoader('app', 'templates'))


@app.listener('before_server_start')
async def init(app, loop):
    app.session = aiohttp.ClientSession(loop=loop)
    app.config.MONGO = AsyncIOMotorClient(config.MONGO, io_loop=loop).sharpbit.sharpbit
    app.oauth = Oauth(
        config.DISCORD_CLIENT_ID,
        config.DISCORD_CLIENT_SECRET,
        scope='identify',
        redirect_uri='https://sharpbit.tk/callback' if not config.DEV else 'http://127.0.0.1:4000/callback',
        session=app.session
    )

@app.listener('after_server_stop')
async def close_session(app, loop):
    await app.session.close()

def get_stack_variable(name):
    stack = inspect.stack()
    try:
        for frames in stack:
            try:
                frame = frames[0]
                current_locals = frame.f_locals
                if name in current_locals:
                    return current_locals[name]
            finally:
                del frame
    finally:
        del stack

async def render_template(template, **kwargs):
    template = env.get_template(template)
    request = get_stack_variable('request')
    kwargs['logged_in'] = request['session'].get('logged_in', False)

    if kwargs['logged_in']:
        coll = app.config.MONGO.user_info
        user = await coll.find_one({'id': request['session'].get('id')})
        kwargs['avatar'] = user.get('avatar_url')
        kwargs['username'] = user.get('name')
        kwargs['discrim'] = user.get('discrim')
        kwargs['theme'] = user.get('theme', 'dark')
    else:
        kwargs['theme'] = 'dark'

    html_content = template.render(**kwargs)
    return response.html(html_content)

app.render_template = render_template

@app.get('/')
async def index(request):
    return await render_template('index.html', description='Home Page')

@app.get('/base32')
async def rickroll(request):
    return response.redirect('https://www.youtube.com/watch?v=dQw4w9WgXcQ')

@app.get('/login')
async def login(request):
    if request['session'].get('logged_in'):
        return response.redirect('/')
    return response.redirect(app.oauth.discord_login_url)

@app.get('/callback')
async def callback(request):
    code = request.raw_args.get('code')
    access_token, expires_in = await app.oauth.get_access_token(code)
    user = await app.oauth.get_user_json(access_token)
    if user.get('message'):
        return await render_template('unauthorized.html', description='Discord Oauth Unauthorized.')

    data = {
        'name': user['username'],
        'discrim': user['discriminator'],
        'id': user['id']
    }

    if user.get('avatar'):
        data['avatar_url'] = 'https://cdn.discordapp.com/avatars/{}/{}.png'.format(user['id'], user['avatar'])
    else: # in case of default avatar users
        data['avatar_url'] = 'https://cdn.discordapp.com/embed/avatars/{}.png'.format(user['discriminator'] % 5)

    coll = request.app.config.MONGO.user_info
    existing_user = await coll.find_one({'id': user.get('id')})
    if not existing_user:
        data['theme'] = 'dark'

    await coll.find_one_and_update({'id': user.get('id')}, {'$set': data}, upsert=True)
    resp = response.redirect('/dashboard')

    request['session']['logged_in'] = True
    request['session']['id'] = user['id']

    return resp

@app.get('/logout')
async def logout(request):
    resp = response.redirect('/')
    del request['session']['logged_in']
    del request['session']['id']
    return resp

@app.get('/invite')
async def invite(request):
    return response.redirect('https://discord.gg/C2tnmHa')

@app.get('/repo/<name>')
async def repo(request, name):
    return response.redirect(f'https://github.com/SharpBit/{name}')

@app.get('/theme')
@login_required()
async def change_theme(request):
    coll = app.config.MONGO.user_info
    theme = (await coll.find_one({'id': request['session']['id']})).get('theme', 'dark')
    await coll.find_one_and_update(
        {'id': request['session']['id']},
        {'$set': {'theme': 'light' if theme == 'dark' else 'dark'}},
        upsert=True
    )
    return response.redirect('/')

@app.get('/shorturl')
async def url_shortener(request):
    return await render_template('url_shortener.html', description='Shorten a URL!')

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

@app.post('/url')
async def url(request):
    coll = request.app.config.MONGO.urls
    code = base36encode(int(time.time() * 1000))
    if request.form.get('code'):
        code = request.form['code'][0]
        existing = await coll.find_one({'code': code})
        if existing:
            return response.text('Error: Code already exists')
    await coll.insert_one({'code': code, 'url': request.form['url'][0], 'id': request['session'].get('id', 'no_account')})
    return response.text(f'Here is your shortened URL: https://sharpbit.tk/{code}')

@app.get('/<code>')
async def short(request, code):
    coll = request.app.config.MONGO.urls
    res = await coll.find_one({'code': code})
    if not res:
        return response.text(f'No such URL shortener code "{code}" found.')
    return response.redirect(res['url'])

@app.get('/pastebin')
async def pastebin_home(request):
    return await render_template('pastebin.html', description='Paste in code for easy access later!')

@app.post('/pb')
async def pb(request):
    coll = request.app.config.MONGO.pastebin
    code = base36encode(int(time.time() * 1000))
    text = request.form['text'][0]
    await coll.insert_one({'code': code, 'text': text, 'id': request['session'].get('id', 'no_account')})
    return response.text(f'Here is your pastebin url: https://sharpbit.tk/pastebin/{code}')

@app.get('/pastebin/<code>')
async def pastebin(request, code):
    coll = request.app.config.MONGO.pastebin
    res = await coll.find_one({'code': code})
    if not res:
        return response.text(f'No such pastebin code "{code}" found.')
    text = res['text'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return await render_template('saved_pastebin.html', code=text)

@app.get('/dashboard')
@login_required()
async def dashboard(request):
    urls = await app.config.MONGO.urls.find({'id': request['session']['id']}).to_list(1000)
    pastes = await app.config.MONGO.pastebin.find({'id': request['session']['id']}).to_list(1000)
    return await render_template('dashboard.html', description='Dashboard for your account.', urls=urls, pastes=pastes)


if __name__ == '__main__':
    app.run(port=4000)
