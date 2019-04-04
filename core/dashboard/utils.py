from sanic import response
from functools import wraps


def login_required():
    def decorator(func):
        @wraps(func)
        async def wrapper(request, *args, **kwargs):
            if not request['session'].get('logged_in'):
                return response.redirect('/login')
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator