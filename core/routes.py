import asyncio
import random
import string
from datetime import date

import brawlstats
from sanic import Blueprint, response

from core.utils import disable_xss, login_required, open_db_connection, render_template
from core.utils import daterange, thisweek

root = Blueprint('root')

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
    if request.ctx.session.get('logged_in'):
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
    url = request.form['url'][0]
    account = request.ctx.session.get('id', 'no_account')

    async with open_db_connection(request.app) as conn:
        if request.form.get('code'):
            code = request.form['code'][0]
            existing = await conn.fetchrow('SELECT * FROM urls WHERE code = $1', code)
            if existing:
                return response.text('Error: Code already exists')
        await conn.execute('INSERT INTO urls(user_id, code, url) VALUES ($1, $2, $3)', account, code, url)
    return response.text(f'Here is your shortened URL: https://{request.app.config.DOMAIN}/{code}')

@root.get('/<code>')
async def existing_code(request, code):
    async with open_db_connection(request.app) as conn:
        res = await conn.fetchrow('SELECT * FROM urls WHERE code = $1', code)
    if not res:
        return response.text(f'No such URL shortener code "{code}" found.')
    return response.redirect(res['url'])

@root.get('/pastebin')
async def pastebin_home(request):
    return await render_template('pastebin', request, title="Pastebin", description='Paste in code for easy access later!')

@root.post('/pastebin/create')
# @authorized()
async def create_pastebin(request):
    chars = string.ascii_letters + string.digits
    code = ''.join(random.choice(chars) for i in range(8))
    text = request.form['text'][0]
    account = request.ctx.session.get('id', 'no_account')
    async with open_db_connection(request.app) as conn:
        await conn.execute('INSERT INTO pastebin(user_id, code, text) VALUES ($1, $2, $3)', account, code, text)
    return response.redirect(f'/pastebin/{code}')

@root.get('/pastebin/<code>')
async def existing_pastebin(request, code):
    async with open_db_connection(request.app) as conn:
        res = await conn.fetchrow('SELECT * FROM pastebin WHERE code = $1', code)
    if not res:
        return response.text(f'No such pastebin code "{code}" found.')
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
        tag = brawlstats.utils.bstag(request.form['tag'][0])
    except brawlstats.NotFoundError as e:
        invalid_chars = e.error.split('\n')
        invalid_chars = invalid_chars[len(invalid_chars) - 1]
        return await render_template(
            template='challenge_home',
            request=request,
            invalid_chars=invalid_chars,
            title='Brawl Stars Challenges',
            description='Search up your tag to view the logs of your Brawl Stars challenge games.'
        )
    return response.redirect(f'/challenges/{tag}')

@root.get('/challenges/<tag>')
async def challenge_stats(request, tag):
    client = request.app.brawl_client
    try:
        logs = await client.get_battle_logs(tag)
    except brawlstats.NotFoundError:
        return await render_template(
            'challenge_stats',
            request,
            tag_found=False,
            entered_tag=disable_xss(tag.upper()),
            title='Brawl Stars Challenges',
            description='View the logs of your Brawl Stars challenge games.'
        )

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
        return await render_template(
            template='challenge_stats',
            request=request,
            tag_found=True,
            games=[],
            len=len,
            title='Brawl Stars Challenges',
            description='View the logs of your Brawl Stars challenge games.'
        )

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
        tag_found=True,
        games=battlelog,
        brawler_key={'EL PRIMO': 'El-Primo', 'MR. P': 'Mr.P'},
        len=len,  # allow len() to be called in the template
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
    print(headers)
    print(f'https://api.brawlstars.com/v1/{endpoint}')
    try:
        async with app.session.get(f'https://api.brawlstars.com/v1/{endpoint}', timeout=30, headers=headers) as resp:
            return response.json(await resp.json(), status=resp.status)
    except asyncio.TimeoutError:
        return response.text('Request failed', status=503)

@root.get('/schoolweek')
async def schoolweek(request):
    first_day = date(2020, 9, 8)
    no_school = [
        date(2020, 9, 28),  # Yom Kippur
        date(2020, 10, 12),  # Columbus day
        date(2020, 11, 3),  # Election day
        date(2020, 11, 11),  # Veteran's day
        *daterange(date(2020, 11, 25), date(2020, 11, 27)),  # Thanksgiving break
        *daterange(date(2020, 12, 24), date(2021, 1, 1))  # Holiday break
    ]
    special_days = [
        date(2020, 10, 2)
    ]

    all_days = []
    day_map = {
        1: 'A',
        0: 'B'
    }

    next_friday = thisweek(date.today())[-1]
    elapsed_dates = daterange(first_day, next_friday)
    mondays = [d for d in elapsed_dates if d.weekday() == 0 and d not in no_school]
    cohort_day = 'maroon'

    for d in elapsed_dates:
        if d in no_school:
            continue
        dow = d.weekday()
        if dow in (5, 6):
            continue
        if dow in (1, 3):
            cohort_day = 'maroon'
        elif dow in (2, 4):
            cohort_day = 'gray'
        elif dow == 0:
            # Mondays
            if d not in mondays:
                continue
            if mondays.index(d) % 2 == 0:
                cohort_day = 'maroon'
            else:
                cohort_day = 'gray'

        try:
            prev_day = [day for day in all_days if day['cohort'] == cohort_day][-1]['day']
        except IndexError:
            # We are adding 1 for the first day of each cohort so we "start" with a B (0) day
            prev_day = 0

        if d in special_days:
            # Skip a day
            all_days.append({
                'cohort': cohort_day,
                'date': d,
                'day': prev_day + 2})
        else:
            all_days.append({
                'cohort': cohort_day,
                'date': d,
                'day': prev_day + 1})


    week = thisweek(date.today())

    week_fmt = []
    for day in week:
        try:
            day_info = list(filter(lambda d: d['date'] == day, all_days))[0]
        except IndexError:
            week_fmt.append(f"{day.strftime('%a %m/%d')}<br>NO SCHOOL")
        else:
            week_fmt.append(f"{day.strftime('%a %m/%d')}<br>{day_info['cohort'].title()} {day_map[day_info['day'] % 2]} day")

    return await render_template('schoolweek', request, week=week_fmt, title='School Week', description='This week\'s maroon and gray A and B days.')
