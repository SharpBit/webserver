from dotenv import load_dotenv, find_dotenv
from sanic.config import Config
import os

load_dotenv(find_dotenv('.env'))


class SiteConfig(Config):
    DEBUG_MODE = os.getenv('DEBUG_MODE') == 'true'
    DISCORD_CLIENT_ID = os.getenv('DISCORD_CLIENT_ID')
    DISCORD_CLIENT_SECRET = os.getenv('DISCORD_CLIENT_SECRET')
    PORT = int(os.getenv('PORT', 4000))
    DOMAIN = 'sharpbit.dev' if not DEBUG_MODE else f'127.0.0.1:{PORT}'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///site.db'
