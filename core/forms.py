from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length

class URLShortenerForm(FlaskForm):
    url = StringField('URL', validators=[DataRequired()])
    code = StringField('Shortened Code', validators=[DataRequired(), Length(min=2, max=50)])
    submit = SubmitField('Submit')


class PastebinForm(FlaskForm):
    text = TextAreaField('Code', validators=[DataRequired()])
    submit = SubmitField('Submit')
