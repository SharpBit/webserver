from dotenv import load_dotenv, find_dotenv
import os

load_dotenv(find_dotenv('.env'))


class Config:
    ENV = os.getenv('ENV')
    DEV = ENV == 'development'
    DISCORD_CLIENT_ID = os.getenv('DISCORD_CLIENT_ID')
    DISCORD_CLIENT_SECRET = os.getenv('DISCORD_CLIENT_SECRET')
    MONGO = os.getenv('MONGO')
    AUTH = os.getenv('AUTH')
    DOMAIN = 'sharpbit.tk' if not DEV else '127.0.0.1:4000'