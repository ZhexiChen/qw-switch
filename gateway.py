"""QW Switch gateway for the documented QwenWork Chat Completions interface."""
import hmac
import json
import os
import secrets
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import switch_config as profiles

MODEL_ID = 'qw-switch'
MODEL_PATH = '/v1/chat/completions'
PORT = int(os.environ.get('QW_SWITCH_PORT', '18747'))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def open_upstream(profile, key, body, session=None, timeout=120):
    payload = {**body, 'model': profile['model']}
    thinking_disabled = payload.get('enable_thinking') is False
    if thinking_disabled:
        payload.pop('reasoning_effort', None)
        if profile['model'].lower().split('/')[-1].startswith('deepseek-'):
            payload.pop('enable_thinking', None)
            payload['thinking'] = {'type': 'disabled'}
    elif profile['effort']:
        payload.pop('enable_thinking', None)
        payload.pop('thinking', None)
        payload['reasoning_effort'] = profile['effort']
    headers = {'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'}
    if profile['kind'] == 'opencodego':
        headers.update({'User-Agent': 'QW-Switch/1.0', 'X-OpenCode-Session': session or str(uuid.uuid4())})
    if profile['kind'] == 'clinepass':
        headers['X-Response-Format'] = 'openai'
    request = urllib.request.Request(profile['endpoint'], data=json.dumps(payload).encode(), headers=headers)
    return urllib.request.build_opener(NoRedirect()).open(request, timeout=timeout)


def connection_key():
    path = profiles.DATA_DIR / 'connection.json'
    profiles.DATA_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        with path.open() as file:
            return json.load(file)['key']
    except FileNotFoundError:
        key = secrets.token_urlsafe(32)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as file:
            json.dump({'key': key}, file)
        return key


class Gateway(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *args):
        pass

    @property
    def origin(self):
        return f'http://127.0.0.1:{self.server.server_port}'

    def is_local_console(self):
        return self.headers.get('Host') == self.origin.removeprefix('http://')

    def send_body(self, status, body, content_type):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if content_type.startswith('text/html'):
            self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; form-action 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def reply(self, status, value):
        self.send_body(status, json.dumps(value).encode(), 'application/json')

    def error(self, status, message):
        self.close_connection = True
        self.reply(status, {'error': {'message': message}})

    def do_GET(self):
        if not self.is_local_console():
            return self.error(403, '控制台仅支持本机访问')
        if self.path == '/qw-switch':
            return self.send_body(200, Path(__file__).with_name('qw-switch.html').read_bytes(), 'text/html; charset=utf-8')
        if self.path == '/qw-switch/state':
            try:
                return self.reply(200, {**profiles.public(), 'connection': {
                    'endpoint': self.origin + MODEL_PATH, 'model': MODEL_ID, 'key': self.server.key}})
            except (OSError, ValueError, KeyError):
                return self.error(503, '无法读取模型配置')
        self.error(404, '接口不存在')

    def read_json(self, limit):
        length = int(self.headers.get('Content-Length', '0'))
        if not 0 < length <= limit:
            raise ValueError('请求大小超出支持范围')
        body = json.loads(self.rfile.read(length))
        if not isinstance(body, dict):
            raise ValueError('请求须为 JSON 对象')
        return body

    def configure(self):
        if not self.is_local_console() or self.headers.get('Origin') != self.origin:
            return self.error(403, '请在本机 QW Switch 页面操作')
        data = self.read_json(65536)
        action = self.path.rsplit('/', 1)[-1]
        if action != 'test':
            return self.reply(200, profiles.change(action, data))
        profile = profiles.find(profiles.read(), data.get('id'))
        key = profiles.key_for(profile)
        if not key:
            raise ValueError('请先配置 API 密钥')
        body = {'messages': [{'role': 'user', 'content': 'Reply only OK.'}], 'max_tokens': 512, 'stream': False}
        with open_upstream(profile, key, body, timeout=30) as upstream:
            result = json.load(upstream)
        if not result.get('choices', [{}])[0].get('message', {}).get('content'):
            return self.error(502, '模型未返回文本')
        self.reply(200, {'ok': True})

    def complete(self):
        authorization = self.headers.get('Authorization', '').encode()
        if not hmac.compare_digest(authorization, ('Bearer ' + self.server.key).encode()):
            return self.error(401, '请使用 QW Switch 的接入密钥')
        body = self.read_json(16 * 1024 * 1024)
        if body.get('model') != MODEL_ID or not isinstance(body.get('messages'), list) or not body['messages']:
            return self.error(400, '请使用 qw-switch 模型 ID 并提供 messages')
        state = profiles.read()
        if not state['active']:
            return self.error(503, '请先在 QW Switch 启用一个模型配置')
        profile = profiles.find(state, state['active'])
        key = profiles.key_for(profile)
        if not key:
            return self.error(503, '当前配置需要模型提供商的 API 密钥')
        session = self.headers.get('X-QwenWork-Session-Id') or self.headers.get('X-Session-Id')
        with open_upstream(profile, key, body, session) as upstream:
            self.send_response(upstream.status)
            self.send_header('Content-Type', upstream.headers.get('Content-Type', 'application/json'))
            self.send_header('Connection', 'close')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.close_connection = True
            while chunk := upstream.read1(8192):
                self.wfile.write(chunk)
                self.wfile.flush()
        print(f'{upstream.status} {profile["kind"]} {profile["model"]}', flush=True)

    def do_POST(self):
        try:
            if self.headers.get_content_type() != 'application/json':
                return self.error(415, '请使用 application/json')
            if self.path.startswith('/qw-switch/'):
                return self.configure()
            if self.path == MODEL_PATH:
                return self.complete()
            self.error(404, '接口不存在')
        except urllib.error.HTTPError as error:
            self.error(502 if error.code < 400 else error.code, f'提供商返回 HTTP {error.code}')
        except (BrokenPipeError, ConnectionResetError):
            pass
        except OSError:
            if not self.close_connection:
                self.error(502, '无法连接提供商或读取本地配置')
        except ValueError as error:
            self.error(400, str(error))
        except (TypeError, KeyError, AttributeError, IndexError):
            self.error(400, '配置或请求无效')


def main():
    with ThreadingHTTPServer(('127.0.0.1', PORT), Gateway) as server:
        server.key = connection_key()
        if ready := os.environ.get('QW_SWITCH_READY_FILE'):
            Path(ready).write_text(str(server.server_port))
        server.serve_forever()


if __name__ == '__main__':
    main()
