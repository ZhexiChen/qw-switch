"""Provider profiles and the active QW Switch route."""
import json
import os
import tempfile
import uuid
from pathlib import Path
from threading import Lock
from urllib.parse import urlsplit

DATA_DIR = Path(os.environ.get('QW_SWITCH_DATA_DIR', Path.home() / 'Library/Application Support/QW Switch Desktop'))
STATE = DATA_DIR / 'profiles.json'
PRESETS = {
    'opencodego': ('OpenCode Go', 'https://opencode.ai/inference/go/openai/v1/chat/completions', 'deepseek-v4.1-flash'),
    'clinepass': ('Cline Pass', 'https://api.cline.bot/api/v1/chat/completions', 'cline-pass/deepseek-v4.1-flash'),
}
EFFORTS = ('', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max')
LOCK = Lock()


def read():
    try:
        return json.loads(STATE.read_text())
    except FileNotFoundError:
        return {'active': None, 'profiles': [
            {'id': kind, 'kind': kind, 'name': name, 'endpoint': endpoint, 'model': model, 'effort': 'max'}
            for kind, (name, endpoint, model) in PRESETS.items()]}


def persist(state):
    STATE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=STATE.parent, delete=False) as tmp:
        temporary = Path(tmp.name)
        try:
            json.dump(state, tmp, ensure_ascii=False, indent=2)
            tmp.close()
            os.replace(temporary, STATE)
        finally:
            temporary.unlink(missing_ok=True)


def find(state, profile_id):
    for profile in state['profiles']:
        if profile['id'] == profile_id:
            return profile
    raise ValueError('找不到模型配置')


def key_for(profile):
    return profile.get('key')


def public():
    state = read()
    return {'active': state['active'], 'profiles': [
        {**{k: p[k] for k in ('id', 'name', 'kind', 'model', 'endpoint', 'effort')},
         'credential': 'saved' if p.get('key') else 'missing'}
        for p in state['profiles']]}


def completion_url(value):
    url = urlsplit(value)
    local = url.hostname in ('localhost', '127.0.0.1', '::1')
    if not url.hostname or url.scheme not in (('https', 'http') if local else ('https',)):
        raise ValueError('请填写 HTTPS API 地址，本机接口可以使用 HTTP')
    if url.username or url.password or url.query or url.fragment:
        raise ValueError('API 地址不能包含账号、查询参数或片段')
    if local and url.port == int(os.environ.get('QW_SWITCH_PORT', '18747')):
        raise ValueError('API 地址不能指向 QW Switch 自己')
    path = url.path.rstrip('/')
    if not path.endswith('/chat/completions'):
        path = (path or '/v1') + '/chat/completions'
    return url._replace(path=path).geturl()


def change(action, data):
    with LOCK:
        state = read()
        if action == 'save':
            previous = find(state, data['id']) if data.get('id') else {}
            kind = data.get('kind', '')
            if kind not in (*PRESETS, 'openai'):
                raise ValueError('请选择连接类型')
            name = data.get('name', '').strip()
            model = data.get('model', '').strip()
            if not name or not model:
                raise ValueError('请填写配置名称和模型 ID')
            effort = data.get('effort', '')
            if effort not in EFFORTS:
                raise ValueError('思考档位无效')
            endpoint = PRESETS[kind][1] if kind in PRESETS else completion_url(data.get('endpoint', '').strip())
            same_provider = kind == previous.get('kind') and (
                urlsplit(endpoint)[:2] == urlsplit(previous['endpoint'])[:2])
            key = data.get('key', '').strip() or (previous.get('key') if same_provider else None)
            profile = {'id': previous.get('id') or uuid.uuid4().hex, 'kind': kind, 'name': name,
                       'endpoint': endpoint, 'model': model, 'effort': effort, **({'key': key} if key else {})}
            if profile['id'] == state['active'] and not key_for(profile):
                raise ValueError('当前配置需要可用的 API 密钥')
            state['profiles'] = [profile if p == previous else p for p in state['profiles']]
            if not previous:
                state['profiles'].append(profile)
        else:
            profile = find(state, data.get('id'))
            if action == 'activate':
                if not key_for(profile):
                    raise ValueError('请先配置 API 密钥')
                state['active'] = profile['id']
            elif action == 'delete':
                if state['active'] == profile['id']:
                    raise ValueError('请先启用其他配置')
                state['profiles'].remove(profile)
            else:
                raise ValueError('未知操作')
        persist(state)
        return public()
