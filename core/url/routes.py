from sanic import Blueprint, response
from core.utils import render_template, open_db_connection, base36encode
import time


url = Blueprint('shortenurl')

@url.get('/urlshortener')
async def url_shortener_home(request):
    return await render_template('url_shortener.html', request, title="URL Shortener", description='Shorten a URL!')

@url.post('/url/create')
async def create_url(request):
    code = base36encode(int(time.time() * 1000))
    url = request.form['url'][0]
    account = request['session'].get('id', 'no_account')

    async with open_db_connection() as conn:
        if request.form.get('code'):
            code = request.form['code'][0]
            existing = await conn.fetchrow('SELECT * FROM urls WHERE code = $1', code)
            if existing:
                return response.text('Error: Code already exists')
        await conn.execute('INSERT INTO urls(id, code, url) VALUES ($1, $2, $3)', account, code, url)
    return response.text(f'Here is your shortened URL: https://sharpbit.tk/{code}')

@url.get('/<code>')
async def existing_code(request, code):
    async with open_db_connection() as conn:
        res = await conn.fetchrow('SELECT * FROM urls WHERE code = $1', code)
    if not res:
        return response.text(f'No such URL shortener code "{code}" found.')
    return response.redirect(res['url'])