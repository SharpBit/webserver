from sanic import Blueprint, response
from core.utils import render_template, base36encode
import time


pastebin = Blueprint('pastebin')

@pastebin.get('/pastebin')
async def pastebin_home(request):
    return await render_template('pastebin.html', request, title="Pastebin", description='Paste in code for easy access later!')

@pastebin.post('/createpastebin')
async def create_pastebin(request):
    coll = request.app.config.MONGO.pastebin
    code = base36encode(int(time.time() * 1000))
    text = request.form['text'][0]
    await coll.insert_one({'code': code, 'text': text, 'id': request['session'].get('id', 'no_account')})
    return response.text(f'Here is your pastebin url: https://sharpbit.tk/pastebin/{code}')

@pastebin.get('/pastebin/<code>')
async def existing_pastebin(request, code):
    coll = request.app.config.MONGO.pastebin
    res = await coll.find_one({'code': code})
    if not res:
        return response.text(f'No such pastebin code "{code}" found.')
    text = res['text'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return await render_template('saved_pastebin.html', request, title="Pastebin - Saved", description="Saved Pastebin", code=text)