class Oauth2:
    def __init__(self, client_id, client_secret, scope=None, redirect_uri=None, session=None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self.redirect_uri = redirect_uri
        self.discord_login_url = 'https://discordapp.com/api/oauth2/authorize?client_id={}&redirect_uri={}&response_type=code&scope={}'.format(client_id, redirect_uri, scope)
        self.discord_token_url = 'https://discordapp.com/api/oauth2/token'
        self.discord_api_url = 'https://discordapp.com/api/v6'
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
