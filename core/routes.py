import asyncio
import random
import smtplib
import string
from datetime import date
from email.message import EmailMessage
from email.mime.text import MIMEText

import brawlstats
from sanic import Blueprint, response
from sanic.exceptions import abort

from core.utils import (add_message, disable_xss, get_school_week,
                        login_required, open_db_connection, render_template)

root = Blueprint('root')

@root.middleware('request')
async def setup_session_dict(request):
    """Sets up session attributes if they do not exist already"""
    if request.ctx.session.get('logged_in', None) is None:
        request.ctx.session['logged_in'] = False

    if request.ctx.session.get('messages', None) is None:
        request.ctx.session['messages'] = []

@root.get('/')
async def index(request):
    async with request.app.session.get('https://api.github.com/users/SharpBit/events/public') as resp:
        info = await resp.json()
    recent_commits = filter(lambda x: x['repo']['name'] != 'SharpBit/modmail' and x['type'] == 'PushEvent', info)
    return await render_template('index', request, title="Home Page", description='Home Page', recent=recent_commits)

@root.get('/invite')
async def invite(request):
    return response.redirect('https://discord.gg/C2tnmHa')

@root.get('/repo/<name>')
async def repo(request, name):
    return response.redirect(f'https://github.com/SharpBit/{name}')


@root.get('/login')
async def login(request):
    if request.ctx.session['logged_in']:
        return response.redirect('/')
    return response.redirect(request.app.oauth.discord_login_url)

@root.get('/callback')
async def callback(request):
    app = request.app
    code = request.args.get('code')
    access_token = await app.oauth.get_access_token(code)
    user = await app.oauth.get_user_json(access_token)
    if user.get('message'):
        return await render_template('unauthorized', request, description='Discord Oauth Unauthorized.')

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

    request.ctx.session['logged_in'] = True
    request.ctx.session['id'] = user['id']

    return response.redirect('/dashboard')

@root.get('/logout')
async def logout(request):
    del request.ctx.session['logged_in']
    del request.ctx.session['id']
    return response.redirect('/')

@root.get('/dashboard')
@login_required()
async def dashboard_home(request):
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
async def url_shortener_home(request):
    return await render_template('url_shortener', request, title='URL Shortener', description='Shorten a URL!')

@root.post('/url/create')
# @authorized()
async def create_url(request):
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
    return add_message(
        request,
        'success',
        f"Shortened URL created at <a href=\"http{'s' if not request.app.config.DEV else ''}://{request.app.config.DOMAIN}/{code}\">"
        f"http{'s' if not request.app.config.DEV else ''}://{request.app.config.DOMAIN}/{code}</a>",
        '/urlshortener'
    )

@root.get('/<code>')
async def existing_code(request, code):
    async with open_db_connection(request.app) as conn:
        res = await conn.fetchrow('SELECT * FROM urls WHERE code = $1', code)
    if not res:
        abort(404, message=f'Requested URL {request.path} not found')
    return response.redirect(res['url'])

@root.get('/pastebin')
async def pastebin_home(request):
    return await render_template('pastebin', request, title="Pastebin", description='Paste in code for easy access later!')

@root.post('/pastebin/create')
# @authorized()
async def create_pastebin(request):
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
async def existing_pastebin(request, code):
    async with open_db_connection(request.app) as conn:
        res = await conn.fetchrow('SELECT * FROM pastebin WHERE code = $1', code)
    if not res:
        abort(404, message=f'Requested URL {request.path} not found')
    text = disable_xss(res['text'])
    return await render_template('saved_pastebin', request, title="Pastebin - Saved", description="Saved Pastebin", code=text)

@root.get('/challenges')
async def challenge_home(request):
    return await render_template(
        template='challenge_home',
        request=request,
        title='Brawl Stars Challenges',
        description='Search up your tag to view the logs of your Brawl Stars challenge games.'
    )

@root.post('/challenges/post')
async def challenge_post(request):
    try:
        form_tag = request.form['tag'][0]
    except KeyError:
        return add_message(request, 'error', 'Enter a player tag.', '/challenges')

    try:
        tag = brawlstats.utils.bstag(form_tag)
    except brawlstats.NotFoundError as e:
        invalid_chars = e.message.split('\n')
        invalid_chars = invalid_chars[-1]
        return add_message(request, 'error', invalid_chars, '/challenges')
    return response.redirect(f'/challenges/{tag}')

@root.get('/challenges/<tag>')
async def challenge_stats(request, tag):
    client = request.app.brawl_client
    try:
        logs = await client.get_battle_logs(tag)
    except brawlstats.NotFoundError:
        return add_message(request, 'error', f'Tag {disable_xss(tag.upper())} was not found.', '/challenges')

    event_map = {
        'gemGrab': 'Gem Grab',
        'brawlBall': 'Brawl Ball',
        'bounty': 'Bounty',
        'heist': 'Heist',
        'siege': 'Siege'
    }

    def filter_challenge_games(battle):
        try:
            if battle.battle.trophy_change == 1 and 'Showdown' not in battle.event.mode:
                return True
        except:
            valid_modes = ['gemGrab', 'brawlBall', 'bounty', 'heist', 'siege']
            if battle.event.mode in valid_modes:
                # Hacky way to filter out ranked matches
                # still possible for a ranked match to be in the result but very unlikely
                for team in battle.battle.teams:
                    for player in team:
                        if player.brawler.trophies % 100 > 3 or player.brawler.power < 10:
                            return False
                return True
        return False

    games = list(filter(filter_challenge_games, logs))[::-1]

    if len(games) == 0:
        return add_message(request, 'error', 'No recent challenge games were found.', '/challenges')

    battlelog = []
    for battle in games:
        battle_info = {
            'event': event_map[battle.event.mode],
            'map': battle.event.map,
            'result': battle.battle.result.title(),
            'teams': battle.battle.teams.to_list()
        }
        for i, team in enumerate(battle_info['teams']):
            for j, player in enumerate(team):
                if player['tag'] == battle.battle.star_player.tag:
                    battle_info['teams'][i][j]['star_player'] = 'star'
                else:
                    battle_info['teams'][i][j]['star_player'] = 'normal'

        battlelog.append(battle_info)
    return await render_template(
        template='challenge_stats',
        request=request,
        games=battlelog,
        brawler_key={'EL PRIMO': 'El-Primo', 'MR. P': 'Mr.P'},
        title='Brawl Stars Challenges',
        description='View the logs of your Brawl Stars challenge games.'
    )

@root.get('/brawlstats/<endpoint:path>')
async def brawlstats_tests_proxy(request, endpoint):
    app = request.app
    endpoint = '/'.join(request.url.split('/')[4:])
    if not request.token:
        return response.text('Invalid authorization', status=403)
    headers = {
        'Authorization': f'Bearer {request.token}',
        'Accept-Encoding': 'gzip'
    }
    try:
        async with app.session.get(f'https://api.brawlstars.com/v1/{endpoint}', timeout=30, headers=headers) as resp:
            return response.json(await resp.json(), status=resp.status)
    except asyncio.TimeoutError:
        return response.text('Request failed', status=503)

@root.get('/schoolweek')
async def schoolweektoday(request):
    return response.redirect(f'/schoolweek/{date.today()}')

@root.get('/schoolweek/<requested_date_str>')
async def schoolweek(request, requested_date_str):
    # TODO: webscrape online calendar to get days off
    # TODO: possibly save days in sql db so email notifs can quickly access the day without processing all the info every time
    requested_date = date(*map(int, requested_date_str.split('-')))
    first_day = date(2020, 9, 8)
    if not first_day <= requested_date <= date(2021, 6, 11):
        abort(404, message=f'Requested URL {request.path} not found')

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
async def email_subscribe(request):
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
    body = MIMEText(
        f"If this wasn't you, click <a href=\"http{'s' if not request.app.config.DEV else ''}://{request.app.config.DOMAIN}"
        f"/schoolweek/unsubscribe/{email}\">here</a> to unsubscribe.", 'html')
    msg.set_content(body)

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(request.app.config.NOREPLY_EMAIL, request.app.config.EMAIL_APP_PASSWORD)

        smtp.send_message(msg)

    async with open_db_connection(request.app) as conn:
        await conn.execute('INSERT INTO mailing_list(email) VALUES ($1)', email)

    return add_message(request, 'success', 'Your email has been added to the mailing list.', '/schoolweek')

@root.get('/schoolweek/unsubscribe/<email>')
async def email_unsubscribe(request, email):
    async with open_db_connection(request.app) as conn:
        await conn.execute('DELETE FROM mailing_list WHERE email = $1', email)
    return add_message(request, 'success', 'Your email has been removed from mailing list.', '/schoolweek')
