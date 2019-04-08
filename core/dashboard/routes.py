from sanic import Blueprint
from core.utils import render_template, open_db_connection
from core.dashboard.utils import login_required


dashboard = Blueprint('dashboard')

@dashboard.get('/dashboard')
@login_required()
async def dashboard_home(request):
    async with open_db_connection() as conn:
        urls = await conn.fetch('SELECT * FROM urls WHERE id = $1', request['session']['id'])
        pastes = await conn.fetch('SELECT * FROM pastebin WHERE id = $1', request['session']['id'])
    return await render_template(
        'dashboard.html',
        request,
        title="Dashboard",
        description='Dashboard for your account.',
        urls=urls,
        pastes=pastes
    )