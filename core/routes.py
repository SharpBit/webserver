import asyncio
import random
import smtplib
import string
from datetime import date
from email.message import EmailMessage
from email.mime.text import MIMEText

from sanic import Blueprint, response
from sanic.exceptions import Forbidden, NotFound, ServerError
from sanic.request import Request

from core.utils import (add_message, disable_xss, get_school_week,
                        login_required, open_db_connection, render_template)

root = Blueprint('root')

@root.middleware('request')
async def setup_session_dict(request: Request):
    """Sets up session attributes if they do not exist already"""
    if request.ctx.session.get('logged_in', None) is None:
        request.ctx.session['logged_in'] = False

    if request.ctx.session.get('messages', None) is None:
        request.ctx.session['messages'] = []

@root.get('/')
async def index(request: Request):
    async with request.app.ctx.aiohttp.get('https://api.github.com/users/SharpBit/events/public') as resp:
        info = await resp.json()
    recent_commits = filter(lambda x: x['type'] == 'PushEvent', info)
    return await render_template('index', request, title="Home Page", description='Home Page', recent=recent_commits)

@root.get('/repo/<name>')
async def repo(request: Request, name: str):
    return response.redirect(f'https://github.com/SharpBit/{name}')

@root.get('/login')
async def login(request: Request):
    if request.ctx.session['logged_in']:
        return response.redirect('/')
    return response.redirect(request.app.ctx.oauth.discord_login_url)

@root.get('/callback')
async def callback(request: Request):
    app = request.app
    code = request.args.get('code')
    access_token = await app.ctx.oauth.get_access_token(code)
    user = await app.ctx.oauth.get_user_json(access_token)
    if user.get('message'):
        return await render_template('unauthorized', request, description='Discord Oauth Unauthorized.')

    if user.get('avatar'):
        avatar = f"https://cdn.discordapp.com/avatars/{user['id']}/{user['avatar']}.png"
    else:  # in case of default avatar users
        avatar = f"https://cdn.discordapp.com/embed/avatars/{user['discriminator'] % 5}.png"

    async with open_db_connection(request.app) as conn:
        await conn.executemany(
            '''INSERT INTO users(id, name, discrim, avatar) VALUES ($1, $2, $3, $4)
            ON CONFLICT (id) DO UPDATE SET id=$1, name=$2, discrim=$3, avatar=$4''',
            [
                (user['id'], user['username'], user['discriminator'], avatar),
                (user['id'], user['username'], user['discriminator'], avatar)
            ]
        )

    request.ctx.session['logged_in'] = True
    request.ctx.session['id'] = user['id']

    return response.redirect('/dashboard')

@root.get('/logout')
async def logout(request: Request):
    del request.ctx.session['logged_in']
    del request.ctx.session['id']
    return response.redirect('/')

@root.get('/dashboard')
@login_required()
async def dashboard_home(request: Request):
    async with open_db_connection(request.app) as conn:
        urls = await conn.fetch('SELECT * FROM urls WHERE user_id = $1', request.ctx.session['id'])
        pastes = await conn.fetch('SELECT * FROM pastebin WHERE user_id = $1', request.ctx.session['id'])
    return await render_template(
        template='dashboard',
        request=request,
        title="Dashboard",
        description='Dashboard for your account.',
        urls=urls,
        pastes=pastes
    )

@root.get('/urlshortener')
async def url_shortener_home(request: Request):
    return await render_template('url_shortener', request, title='URL Shortener', description='Shorten a URL!')

@root.post('/url/create')
# @authorized()
async def create_url(request: Request):
    chars = string.ascii_letters + string.digits
    code = ''.join(random.choice(chars) for i in range(8))
    try:
        url = request.form['url'][0]
    except KeyError:
        return add_message(request, 'error', 'Enter a URL to redirect to.', '/urlshortener')
    account = request.ctx.session.get('id', 'no_account')

    async with open_db_connection(request.app) as conn:
        if request.form.get('code'):
            code = request.form['code'][0]
            existing = await conn.fetchrow('SELECT * FROM urls WHERE code = $1', code)
            if existing:
                return add_message(request, 'error', 'That code is already taken. Try another one.', '/urlshortener')
        await conn.execute('INSERT INTO urls(user_id, code, url) VALUES ($1, $2, $3)', account, code, url)
    secure = 's' if not request.app.config.DEV else ''
    return add_message(
        request,
        'success',
        f"Shortened URL created at <a href=\"http{secure}://{request.app.config.DOMAIN}/{code}\">"
        f"http{'s' if not request.app.config.DEV else ''}://{request.app.config.DOMAIN}/{code}</a>",
        '/urlshortener'
    )

@root.get('/<code>')
async def existing_code(request: Request, code: str):
    async with open_db_connection(request.app) as conn:
        res = await conn.fetchrow('SELECT * FROM urls WHERE code = $1', code)
    if not res:
        raise NotFound(message=f'Requested URL {request.path} not found')
    return response.redirect(res['url'])

@root.get('/pastebin')
async def pastebin_home(request: Request):
    return await render_template('pastebin', request, title="Pastebin",
                                 description='Paste some code for easy access later!')

@root.post('/pastebin/create')
# @authorized()
async def create_pastebin(request: Request):
    chars = string.ascii_letters + string.digits
    code = ''.join(random.choice(chars) for i in range(8))
    try:
        text = request.form['text'][0]
    except KeyError:
        return add_message(request, 'error', 'Paste some code in to save.', '/pastebin')
    account = request.ctx.session.get('id', 'no_account')
    async with open_db_connection(request.app) as conn:
        await conn.execute('INSERT INTO pastebin(user_id, code, text) VALUES ($1, $2, $3)', account, code, text)
    return response.redirect(f'/pastebin/{code}')

@root.get('/pastebin/<code>')
async def existing_pastebin(request: Request, code: str):
    async with open_db_connection(request.app) as conn:
        res = await conn.fetchrow('SELECT * FROM pastebin WHERE code = $1', code)
    if not res:
        raise NotFound(message=f'Requested URL {request.path} not found')
    text = disable_xss(res['text'])
    return await render_template(
        template='saved_pastebin',
        request=request,
        title="Pastebin - Saved",
        description="Saved Pastebin",
        code=text
    )

@root.get('/brawlstats/<endpoint:path>')
async def brawlstats_tests_proxy(request: Request, endpoint: str):
    endpoint = '/'.join(request.url.split('/')[4:])
    if not request.token:
        raise Forbidden('Invalid authorization')
    headers = {
        'Authorization': f'Bearer {request.token}',
        'Accept-Encoding': 'gzip'
    }
    try:
        async with request.app.ctx.aiohttp.get(
            f'https://api.brawlstars.com/v1/{endpoint}',
            timeout=30,
            headers=headers
        ) as resp:
            return response.json(await resp.json(), status=resp.status)
    except asyncio.TimeoutError:
        raise ServerError('Request failed', status_code=503)

@root.get('/schoolweek')
async def schoolweektoday(request: Request):
    return response.redirect(f'/schoolweek/{date.today()}')

@root.get('/schoolweek/<requested_date_str>')
async def schoolweek(request: Request, requested_date_str: str):
    requested_date = date(*map(int, requested_date_str.split('-')))
    first_day = date(2020, 9, 8)
    if not first_day <= requested_date <= date(2021, 3, 11):
        raise NotFound(f'Requested URL {request.path} not found. Maybe try a date between 9/8/2020 and 3/11/2021?')

    week_fmt = await get_school_week(requested_date, first_day, week=True)

    return await render_template(
        template='schoolweek',
        request=request,
        week=week_fmt,
        requested_date=requested_date,
        title='School Week',
        description='This week\'s maroon and gray A and B days.'
    )


@root.post('/schoolweek/subscribe')
# @authorized()
async def email_subscribe(request: Request):
    try:
        email = request.form['email'][0]
    except KeyError:
        return add_message(request, 'error', 'Enter an email in the field.', '/schoolweek')

    async with open_db_connection(request.app) as conn:
        existing = await conn.fetchrow('SELECT * FROM mailing_list WHERE email = $1', email)
        if existing:
            return add_message(request, 'error', 'Email already subscribed.', '/schoolweek')

    msg = EmailMessage()
    msg['Subject'] = 'Thank you for subscribing to GCHS Daily Updates!'
    msg['From'] = request.app.config.CUSTOM_EMAIL
    msg['To'] = email
    secure = 's' if not request.app.config.DEV else ''
    body = MIMEText(
        f"If this wasn't you, click <a href=\"http{secure}://{request.app.config.DOMAIN}"
        f"/schoolweek/unsubscribe/{email}\">here</a> to unsubscribe.", 'html')
    msg.set_content(body)

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(request.app.config.NOREPLY_EMAIL, request.app.config.EMAIL_APP_PASSWORD)

        smtp.send_message(msg)

    async with open_db_connection(request.app) as conn:
        await conn.execute('INSERT INTO mailing_list(email) VALUES ($1)', email)

    return add_message(request, 'success', 'Your email has been added to the mailing list.', '/schoolweek')

@root.get('/schoolweek/unsubscribe/<email>')
async def email_unsubscribe(request: Request, email: str):
    async with open_db_connection(request.app) as conn:
        await conn.execute('DELETE FROM mailing_list WHERE email = $1', email)
    return add_message(request, 'success', 'Your email has been removed from mailing list.', '/schoolweek')
