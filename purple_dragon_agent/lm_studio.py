from __future__ import annotations
import json
from datetime import datetime,timezone
import ipaddress
import urllib.request
import urllib.error
from urllib.parse import urlsplit

class LMStudioError(RuntimeError):
    def __init__(self, message, code='request_failed'):
        super().__init__(message)
        self.code=code

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

class LMStudioClient:
    def __init__(self, endpoint: str, model: str, temperature: float = 0.2, timeout_seconds: int = 60, max_tokens: int = 2048):
        if not isinstance(endpoint,str) or not endpoint or len(endpoint)>2000:
            raise ValueError('Model endpoint must be bounded text.')
        if not isinstance(model,str) or not model.strip() or len(model)>512:
            raise ValueError('Model identifier must contain 1–512 characters.')
        if type(temperature) not in (int,float) or not 0 <= temperature <= 2:
            raise ValueError('Model temperature must be between 0 and 2.')
        if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 300:
            raise ValueError('Model timeout must be between 1 and 300 seconds.')
        parsed = urlsplit(endpoint)
        try: port=parsed.port
        except ValueError as exc:raise ValueError('Model endpoint port is invalid.') from exc
        if parsed.query or parsed.fragment:
            raise ValueError('Model endpoint must not contain query parameters or fragments.')
        try:
            local = ipaddress.ip_address(parsed.hostname or '').is_loopback
        except ValueError:
            local = parsed.hostname == 'localhost'
        if parsed.scheme not in {'http', 'https'} or not local or parsed.username or parsed.password:
            raise ValueError('LM Studio endpoint must use HTTP(S) on localhost or a loopback address.')
        if type(max_tokens) is not int or not 1 <= max_tokens <= 16384:
            raise ValueError('Response limit must be between 1 and 16,384 tokens.')
        self.max_tokens=max_tokens
        self.last_finish_reason=None
        self.last_request=None
        self.endpoint = endpoint
        self.model = model
        self.temperature = temperature
        self.timeout_seconds = timeout_seconds

    def chat(self, system: str, user: str, *, max_tokens: int | None = None) -> str:
        body = {'model': self.model, 'temperature': self.temperature,
                'messages': [{'role':'system','content':system}, {'role':'user','content':user}]}
        limit=self.max_tokens if max_tokens is None else max_tokens
        if type(limit) is not int or not 1 <= limit <= 16384:
            raise ValueError('Response limit must be between 1 and 16,384 tokens.')
        body['max_tokens']=limit
        self.last_finish_reason=None
        serialized=json.dumps(body).encode('utf-8')
        self.last_request={'attempted_at':datetime.now(timezone.utc).isoformat(),'status':'attempted','request_json':serialized[:4_000_000].decode('utf-8',errors='replace'),'truncated':len(serialized)>4_000_000,'note':'Last attempted request, not proof of server receipt or use. Session only; may include selected source, saved memory and conversation reference. Cleared when connector/settings/workspace is rebuilt.'}
        req = urllib.request.Request(self.endpoint, data=serialized,
                                     headers={'Content-Type':'application/json'}, method='POST')
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        try:
            with opener.open(req, timeout=self.timeout_seconds) as resp:
                raw = resp.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise LMStudioError('Model response exceeds the size limit.')
                payload = json.loads(raw.decode('utf-8'))
            content = payload['choices'][0]['message']['content']
            if not isinstance(content, str):
                raise LMStudioError('Model content must be text.')
            reason=payload['choices'][0].get('finish_reason')
            self.last_finish_reason=reason if reason in {'stop','length','tool_calls','content_filter'} else None
            self.last_request['status']='returned_text'
            return content
        except LMStudioError:
            self.last_request['status']='failed'
            raise
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError, IndexError, TypeError) as exc:
            if isinstance(exc, urllib.error.HTTPError):
                exc.close()
            self.last_request['status']='failed'
            timeout=isinstance(exc,TimeoutError) or (isinstance(exc,urllib.error.URLError) and isinstance(exc.reason,TimeoutError))
            code='timeout' if timeout else 'http_error' if isinstance(exc,urllib.error.HTTPError) else 'invalid_response'
            raise LMStudioError(f'Invalid or unavailable local model response: {exc}',code) from exc
