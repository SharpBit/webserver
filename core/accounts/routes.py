from sanic import Blueprint, response
from core.utils import render_template, open_db_connection


account = Blueprint('accounts')

@account.get('/login')
async def login(request):
    if request['session'].get('logged_in'):
        return response.redirect('/')
    return response.redirect(request.app.oauth.discord_login_url)

@account.get('/callback')
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

@account.get('/logout')
async def logout(request):
    del request['session']['logged_in']
    del request['session']['id']
    return response.redirect('/')