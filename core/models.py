from core import db

class DiscordUser(db.Model):
    __tablename__ = 'users'
    user_id = db.Column(db.BigInteger, primary_key=True)
    name = db.Column(db.String(32), nullable=False)
    avatar = db.Column(db.Text, nullable=False)

    def __repr__(self):
        return f'DiscordUser({self.user_id=}, {self.name=})'
