from sanic import Sanic
from sanic_session import Session

from core.config import Config

from core.routes import root
from core.listeners import listeners
# from core.utils import handle_daily_emails


def create_app(config_class=Config):
    app = Sanic(__name__)
    app.config.from_object(Config)

    # Host static files
    app.static('/static', './core/static')
    app.static('/js', './core/js')

    # Blueprints
    app.blueprint(root)
    app.blueprint(listeners)

    Session(app)  # sanic_session
    # app.add_task(handle_daily_emails)

    return app