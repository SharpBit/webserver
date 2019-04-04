from sanic import Blueprint
from core.utils import render_template
from core.dashboard.utils import login_required


dashboard = Blueprint('dashboard')

@dashboard.get('/dashboard')
@login_required()
async def dashboard_home(request):
    app = request.app
    urls = await app.config.MONGO.urls.find({'id': request['session']['id']}).to_list(1000)
    pastes = await app.config.MONGO.pastebin.find({'id': request['session']['id']}).to_list(1000)
    return await render_template(
        'dashboard.html',
        request,
        title="Dashboard",
        description='Dashboard for your account.',
        urls=urls,
        pastes=pastes
    )