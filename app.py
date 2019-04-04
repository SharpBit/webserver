from sanic import Sanic
from sanic_session import Session

# Import blueprints
from core import home, listeners, account, dashboard, pastebin, url
from core.config import Config


if __name__ == '__main__':
    app = Sanic(__name__)

    # Host static files
    app.static('/static', './static')
    app.static('/js', './js')
    app.static('/favicon.ico', './static/favicon.ico')

    # Blueprints
    app.blueprint(home)
    app.blueprint(listeners)
    app.blueprint(account)
    app.blueprint(dashboard)
    app.blueprint(pastebin)
    app.blueprint(url)

    Session(app)  # Sanic session

    if Config.DEV:
        app.run(port=4000, debug=True)
    else:
        app.run(port=4000, debug=False)
