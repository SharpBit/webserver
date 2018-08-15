from sanic import response, Sanic

from functools import wraps

import aiohttp
import asyncio
import base64
import unidecode

import json
import os
import re

app = Sanic(__name__)

with open('data/status_codes.json') as f:
    app.status_codes = json.load(f)


def authorized():
    def decorator(f):
        @wraps(f)
        async def decorated_function(request, *args, **kwargs):
            if request.token == 'hunter2':
                return await f(request, *args, **kwargs)
            return response.json({'error': True, 'message': 'Unauthorized'}, status=401)
        return decorated_function
    return decorator


async def websocket_handler(url, headers, session):
    async with session.ws_connect(url, headers=headers, heartbeat=1, timeout=30) as ws:
        print('Websocket connected!')
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                message = msg.data
                message = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', message)

                message_data = json.loads(message)

                if message_data.get('error') == 'Auth not valid':
                    print('Connection settings invalid.')
                elif message_data.get('type') != 'interaction':
                    if message_data['type'] == 'question':
                        question_str = unidecode(message_data['question'])
                        answers = [unidecode(ans['text']) for ans in message_data['answers']]
                        with open('data/hq_questions.json') as f:
                            data = json.load(f)
                            info = {
                                'question': question_str,
                                'answers': answers,
                                'question_num': message_data['questionNumber']
                            }
                            data.append(info)
                            json.dump(data)
                        git_commit(session)


async def git_commit(session):
    url = 'https://api.github.com/repos/SharpBit/HQ-Bot/contents/data/hq_questions.json'
    base64content = base64.b64encode(open('data/hq_questions.json', "rb").read())
    async with session.get(url + '?ref=master', headers={'Authorization': 'token ' + os.environ.get('github-token')}).json() as data:
        sha = data['sha']
    if base64content.decode('utf-8') + '\n' != data['content']:
        message = json.dumps({
            'message': 'update',
            'branch': 'master',
            'content': base64content.decode('utf-8'),
            'sha': sha
        })

        async with session.put(url, data=message, headers={'Content-Type': 'application/json', 'Authorization': 'token ' + os.environ.get('github-token')}) as resp:
            print(resp)
    else:
        print('Nothing to update.')


async def get_questions(session):

    BEARER_TOKEN = os.environ.get('bearer-token')

    main_url = 'https://api-quiz.hype.space/shows/now?type=hq'
    headers = {'Authorization': f'Bearer {BEARER_TOKEN}',
               'x-hq-client': 'Android/1.3.0'}
    # 'x-hq-stk': 'MQ==',
    # 'Connection': 'Keep-Alive',
    # 'User-Agent': 'okhttp/3.8.0'}

    async with session.get(main_url, headers=headers, timeout=1.5) as resp:
        response_data = await resp.json()

    if response_data.get('broadcast'):
        socket = response_data['broadcast']['socketUrl']
        await websocket_handler(socket, headers=headers, session=session)
    else:
        await asyncio.sleep(5)


@app.listener('before_server_start')
async def create_session(app, loop):
    app.session = aiohttp.ClientSession(loop=loop)


@app.listener('after_server_start')
async def search_questions(app, loop):
    loop.create_task(get_questions(app.session))


@app.listener('after_server_stop')
async def close_session(app, loop):
    await app.session.close()


@app.route('/')
# @authorized()
async def index(request):
    return response.json({'hello': 'world'})


@app.route('/status/<status>')
async def status_code(request, status):
    try:
        info = app.status_codes[status]
    except KeyError:
        return response.json({'error': True, 'status': status, 'message': 'invalid status'})
    else:
        return response.json({'error': False, 'status': status, 'info': info})


@app.route('/hq')
async def hq_home(request):
    return response.json({'endpoints': ['/questions', '/answer']})


@app.route('/hq/questions')
# @authorized()
async def load_questions(request):
    with open('data/hq_questions.json') as f:
        questions = json.load(f)
    return response.json(questions)


@app.route('/hq/answer', methods=['POST'])
# @authorized()
async def submit_answer(request):
    with open('data/hq_questions.json') as f:
        questions = json.load(f)
    question = request.json.get('question')
    for q in questions:
        if question.lower() == q['question'].lower():
            q['answer'] = request.json.get('answer')
    git_commit(app.session)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.getenv('PORT') or 5000)
