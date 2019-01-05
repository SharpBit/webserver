from dotenv import load_dotenv, find_dotenv
from functools import wraps
from sanic import response

import os


load_dotenv(find_dotenv('.env'))

def authorized():
    def decorator(f):
        @wraps(f)
        async def decorated_function(request, *args, **kwargs):
            if request.token == os.getenv('AUTH_TOKEN'):
                return await f(request, *args, **kwargs)
            return response.json({'error': True, 'message': 'Unauthorized'}, status=401)
        return decorated_function
    return decorator