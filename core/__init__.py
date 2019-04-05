from sanic import Sanic
from sanic_session import Session

from core.config import Config

# Routes
from core.accounts.routes import account
from core.dashboard.routes import dashboard
from core.main.routes import home
from core.main.listeners import listeners
from core.pastebin.routes import pastebin
from core.url.routes import url


def create_app(config_class=Config):
    app = Sanic(__name__)
    app.config.from_object(Config)

    # Host static files
    app.static('/core', './core')

    # Blueprints
    app.blueprint(home)
    app.blueprint(listeners)
    app.blueprint(account)
    app.blueprint(dashboard)
    app.blueprint(pastebin)
    app.blueprint(url)

    Session(app)  # sanic_session

    return app