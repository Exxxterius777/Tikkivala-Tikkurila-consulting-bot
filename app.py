from flask import Flask, render_template, request, jsonify
from bot_logic import route_message

app = Flask(__name__)


@app.route('/')
def index():
    return render_template('chat.html')


@app.route('/api/message', methods=['POST'])
def api_message():
    data = request.get_json() or {}
    user_message = data.get('message', '').strip()
    client_stage = data.get('stage', 'start')
    client_context = data.get('context') or {}

    if not user_message:
        return jsonify({'reply': 'Пожалуйста, напишите сообщение.',
                        'stage': client_stage, 'context': client_context})

    # Диагностика: печатаем в консоль PyCharm, что происходит
    print(f"[DEBUG] in  msg={user_message[:40]!r}  stage={client_stage}")

    reply, new_stage, new_context = route_message(
        user_message,
        stage=client_stage,
        context=client_context,
    )

    print(f"[DEBUG] out stage={new_stage}  reply={reply[:40]!r}")

    # ВАЖНО: вынимаем link и map_url из контекста,
    # чтобы они не сохранялись на клиенте и не «залипали» на следующих сообщениях
    response = {'reply': reply, 'stage': new_stage}
    link = new_context.pop('link', None)
    map_url = new_context.pop('map_url', None)
    if link:
        response['link'] = link
    if map_url:
        response['map_url'] = map_url
    response['context'] = new_context

    return jsonify(response)


if __name__ == '__main__':
    app.run(debug=True, port=5000)