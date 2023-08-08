from flask import Flask
from flask_sqlalchemy import SQLAlchemy

from core.config import SiteConfig

def create_app():
    app = Flask('sharpbit_dev')
    app.config.from_object(SiteConfig)
    db = SQLAlchemy(app)
    with app.app_context():
        db.create_all()
