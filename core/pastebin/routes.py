from sanic import Blueprint, response
from core.utils import render_template, open_db_connection, base36encode
import time


pastebin = Blueprint('pastebin')

@pastebin.get('/pastebin')
async def pastebin_home(request):
    return await render_template('pastebin.html', request, title="Pastebin", description='Paste in code for easy access later!')

@pastebin.post('/pastebin/create')
async def create_pastebin(request):
    code = base36encode(int(time.time() * 1000))
    text = request.form['text'][0]
    account = request['session'].get('id', 'no_account')
    async with open_db_connection() as conn:
        await conn.execute('INSERT INTO pastebin(id, code, text) VALUES ($1, $2, $3)', account, code, text)
    return response.text(f'Here is your pastebin url: https://sharpbit.tk/pastebin/{code}')

@pastebin.get('/pastebin/<code>')
async def existing_pastebin(request, code):
    async with open_db_connection() as conn:
        res = await conn.fetchrow('SELECT * FROM pastebin WHERE code = $1', code)
    if not res:
        return response.text(f'No such pastebin code "{code}" found.')
    text = res['text'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return await render_template('saved_pastebin.html', request, title="Pastebin - Saved", description="Saved Pastebin", code=text)