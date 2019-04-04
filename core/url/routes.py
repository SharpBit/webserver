from sanic import Blueprint, response
from core.utils import render_template, base36encode
import time


url = Blueprint('shortenurl')

@url.get('/urlshortener')
async def url_shortener_home(request):
    return await render_template('url_shortener.html', request, title="URL Shortener", description='Shorten a URL!')

@url.post('/createurl')
async def create_url(request):
    coll = request.app.config.MONGO.urls
    code = base36encode(int(time.time() * 1000))
    if request.form.get('code'):
        code = request.form['code'][0]
        existing = await coll.find_one({'code': code})
        if existing:
            return response.text('Error: Code already exists')
    await coll.insert_one({'code': code, 'url': request.form['url'][0], 'id': request['session'].get('id', 'no_account')})
    return response.text(f'Here is your shortened URL: https://sharpbit.tk/{code}')

@url.get('/<code>')
async def existing_code(request, code):
    coll = request.app.config.MONGO.urls
    res = await coll.find_one({'code': code})
    if not res:
        return response.text(f'No such URL shortener code "{code}" found.')
    return response.redirect(res['url'])