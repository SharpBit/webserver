import asyncio
import smtplib
import traceback
from contextlib import asynccontextmanager
from datetime import date, datetime
from datetime import time as dt_time
from datetime import timedelta
from email.message import EmailMessage
from email.mime.text import MIMEText
from functools import wraps

import asyncpg
from jinja2 import Environment, PackageLoader
from sanic import response


class Oauth2:
    def __init__(self, client_id, client_secret, scope=None, redirect_uri=None, session=None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self.redirect_uri = redirect_uri
        self.discord_login_url = 'https://discord.com/api/oauth2/authorize?client_id={}&redirect_uri={}&response_type=code&scope={}'.format(client_id, redirect_uri, scope)
        self.discord_token_url = 'https://discord.com/api/oauth2/token'
        self.discord_api_url = 'https://discord.com/api/v6'
        self.session = session

    async def get_access_token(self, code):
        payload = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': self.redirect_uri,
            'scope': self.scope
        }

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        async with self.session.post(self.discord_token_url, data=payload, headers=headers) as z:
            resp = await z.json()
        return resp.get('access_token')

    async def get_user_json(self, access_token):
        url = self.discord_api_url + '/users/@me'

        headers = {
            'Authorization': 'Bearer {}'.format(access_token)
        }

        async with self.session.get(url, headers=headers) as z:
            resp = await z.json()
        return resp


@asynccontextmanager
async def open_db_connection(app, **options):
    user = options.pop('user', app.config.DB_USERNAME)
    password = options.pop('password', app.config.DB_PASSWORD)
    database = options.pop('database', app.config.DB_NAME)
    host = options.pop('host', app.config.DB_HOST)

    # try:
    conn = await asyncpg.connect(user=user, password=password, database=database, host=host)
    yield conn
    # finally:
    await conn.close()

async def render_template(template, request, **context):
    """
    Function to return jinja variables to the html
    """
    env = Environment(loader=PackageLoader('core', 'templates'))
    template = env.get_template(template + '.html')
    context['logged_in'] = request.ctx.session['logged_in']

    if context['logged_in']:
        async with open_db_connection(request.app) as conn:
            user = await conn.fetchrow('SELECT * FROM users WHERE id = $1', request.ctx.session['id'])
        context['avatar'] = user['avatar']
        context['username'] = user['name']
        context['discrim'] = user['discrim']
    context['messages'] = request.ctx.session['messages']

    html_content = template.render(**context)
    request.ctx.session['messages'] = []  # Clear messages after every request
    return response.html(html_content)

def add_message(request, category, message, redirect_to=None):
    """Add a flash message to appear at the top of a page and redirect to an endpoint if provided"""
    request.ctx.session['messages'].append([category, message])
    if redirect_to:
        return response.redirect(redirect_to)


def disable_xss(content):
    """Prevent cross-site scripting"""
    return content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def login_required():
    def decorator(func):
        @wraps(func)
        async def wrapper(request, *args, **kwargs):
            if not request.ctx.session['logged_in']:
                return response.redirect('/login')
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator

def authorized():
    def decorator(f):
        @wraps(f)
        async def decorated_function(request, *args, **kwargs):
            if request.token == request.app.config.REQUEST_TOKEN:
                return await f(request, *args, **kwargs)
            return response.json({'error': True, 'message': 'Unauthorized'}, status=401)
        return decorated_function
    return decorator


def daterange(start_date: date, end_date: date) -> list:
    """Creates a list of dates from the start date to end date, inclusive"""
    day_count = (end_date - start_date).days + 1
    return [start_date + timedelta(days=i) for i in range(day_count)]



def thisweek(today: date) -> list:
    """Gets a list of dates for this week"""
    if 0 <= today.weekday() <= 4:
        # Monday to Friday
        monday = today - timedelta(days=today.weekday())  # Last Monday
    else:
        monday = today - timedelta(days=today.weekday() - 7)
    friday = monday + timedelta(days=4)

    return daterange(monday, friday)


async def get_school_week(requested_date: date, first_day: date, week=True):
    no_school = [
        date(2020, 9, 28),  # Yom Kippur
        date(2020, 10, 12),  # Columbus day
        date(2020, 11, 3),  # Election day
        date(2020, 11, 11),  # Veteran's day
        *daterange(date(2020, 11, 25), date(2020, 11, 27)),  # Thanksgiving break
        *daterange(date(2020, 12, 24), date(2021, 1, 1)),  # Holiday break
        date(2021, 1, 18),  # Martin Luther King Day
        *daterange(date(2021, 2, 15), date(2021, 2, 19))  # Winter break
    ]
    special_days = [
        date(2020, 10, 2),
        date(2021, 2, 1)  # Snow day 2 (first snow day didn't affect A/B days)
    ]

    all_days = []
    day_map = {
        1: 'A',
        0: 'B'
    }

    next_friday = thisweek(requested_date)[-1]
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


    this_week = thisweek(requested_date)

    if week:
        week_fmt = []
        for day in this_week:
            try:
                day_info = list(filter(lambda d: d['date'] == day, all_days))[0]
            except IndexError:
                week_fmt.append(f"{day.strftime('%a %m/%d')}<br>NO SCHOOL")
            else:
                week_fmt.append(f"{day.strftime('%a %m/%d')}<br>{day_info['cohort'].title()} {day_map[day_info['day'] % 2]} day")
        return week_fmt

    try:
        day_info = list(filter(lambda d: d['date'] == requested_date, all_days))[0]
    except IndexError:
        # No school
        return None
    day_info['day'] = day_map[day_info['day'] % 2]
    return day_info


async def handle_daily_emails(app):
    """Send out an email at a specified time every weekday"""
    today = date.today()
    # Saturday/Sunday
    if today.weekday() in (5, 6):
        today = today - timedelta(days=today.weekday() - 7)  # Not actually today, next monday
    next_email = datetime.combine(today, dt_time(7, 0, 0))

    # Past the time today, send "tomorrow"
    if next_email < datetime.now():
        next_email = datetime.combine(today + timedelta(days=1), dt_time(7, 0, 0))

    delta = (next_email - datetime.now()).seconds
    await asyncio.sleep(delta)

    today = date.today()  # next day after sleeping
    if today.weekday() in (5, 6):
        # Could be here if the func was called after the time on Friday
        return app.add_task(handle_daily_emails)


    today_info = await get_school_week(today, date(2020, 9, 8), week=False)
    if today_info is None:
        # No school
        await asyncio.sleep(1)
        return app.add_task(handle_daily_emails)

    async with open_db_connection(app) as conn:
        emails = await conn.fetch('SELECT * FROM mailing_list')

    messages = []
    for email in emails:
        msg = EmailMessage()
        msg['Subject'] = f"GCHS Daily Email Notification  for {today.strftime('%m/%d/%Y')}"
        msg['From'] = app.config.CUSTOM_EMAIL
        msg['To'] = email
        body = MIMEText(
            f"Today, {today.strftime('%m/%d/%Y')}, is a {today_info['cohort'].title()} {today_info['day']} day. <br><br>"
            f"Click <a href=\"http{'s' if not app.config.DEV else ''}://{app.config.DOMAIN}"
            f"/schoolweek/unsubscribe/{msg['To']}\">here</a> to unsubscribe.", 'html')

        msg.set_content(body)
        messages.append(msg)

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        try:
            smtp.login(app.config.NOREPLY_EMAIL, app.config.EMAIL_APP_PASSWORD)
        except smtplib.SMTPAuthenticationError:
            # Prevent failure of email scheduling if Google's servers crash (like on 12/14/20)
            print(traceback.format_exc())
        else:
            for msg in messages:
                smtp.send_message(msg)

    # Prevent it from sending twice
    await asyncio.sleep(1)
    app.add_task(handle_daily_emails)
