from sanic import Blueprint, response
from core.utils import render_template


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
    access_token, expires_in = await app.oauth.get_access_token(code)
    user = await app.oauth.get_user_json(access_token)
    if user.get('message'):
        return await render_template('unauthorized.html', request, description='Discord Oauth Unauthorized.')

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

    await coll.find_one_and_update({'id': user.get('id')}, {'$set': data}, upsert=True)
    resp = response.redirect('/dashboard')

    request['session']['logged_in'] = True
    request['session']['id'] = user['id']

    return resp

@account.get('/logout')
async def logout(request):
    del request['session']['logged_in']
    del request['session']['id']
    return response.redirect('/')