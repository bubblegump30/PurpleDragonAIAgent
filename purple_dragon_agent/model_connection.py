"""Explicit bounded loopback-only discovery and a tiny inference smoke test."""
from datetime import datetime,timezone
import json
import socket
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit,urlunsplit
from .lm_studio import LMStudioClient,LMStudioError,NoRedirect


class ConnectionFailure(RuntimeError):
    def __init__(self,code,message,details=None):
        super().__init__(message);self.code=code;self.details=details or {}


def models_url(endpoint):
    # Reuse the connector's authority validation; never follow redirects or proxies.
    LMStudioClient(endpoint,'connection-probe')
    parsed=urlsplit(endpoint)
    if parsed.query or parsed.fragment:
        raise ValueError('The local endpoint must not contain query parameters or fragments.')
    path=parsed.path.rstrip('/')
    if path.endswith('/chat/completions'):
        path=path[:-len('/chat/completions')]
    if not path.endswith('/v1'):
        raise ValueError('Use the OpenAI-compatible /v1/chat/completions endpoint.')
    return urlunsplit((parsed.scheme,parsed.netloc,path+'/models','',''))


def discover_models(endpoint,timeout=5):
    url=models_url(endpoint)
    started=time.monotonic()
    request=urllib.request.Request(url,headers={'Accept':'application/json'},method='GET')
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    try:
        with opener.open(request,timeout=timeout) as response:
            raw=response.read(262145)
        if len(raw)>262144:
            raise ConnectionFailure('invalid_response','The model list exceeds the response size limit.')
        payload=json.loads(raw.decode('utf-8'))
        if not isinstance(payload,dict) or not isinstance(payload.get('data'),list) or len(payload['data'])>256:
            raise ConnectionFailure('invalid_response','The server did not return a valid bounded model list.')
        identifiers=[]
        for row in payload['data']:
            if not isinstance(row,dict) or not isinstance(row.get('id'),str) or not row['id'].strip() or len(row['id'])>512:
                raise ConnectionFailure('invalid_response','A model identifier is invalid.')
            if row['id'] not in identifiers:identifiers.append(row['id'])
        return {'models':identifiers,'latency_ms':round((time.monotonic()-started)*1000),'checked_at':datetime.now(timezone.utc).isoformat()}
    except urllib.error.HTTPError as exc:
        exc.close()
        if exc.code in (401,403):
            raise ConnectionFailure('authentication','The local server requires authentication. This release has no server-token configuration.') from exc
        if 300<=exc.code<400:
            raise ConnectionFailure('redirect_blocked','The local server attempted a redirect; redirects are blocked.') from exc
        if exc.code==404:
            raise ConnectionFailure('endpoint','Model-list endpoint not found. Check the server port and /v1/chat/completions path.') from exc
        raise ConnectionFailure('server_error',f'The local server returned HTTP {exc.code}.') from exc
    except (TimeoutError,socket.timeout) as exc:
        raise ConnectionFailure('timeout','The local server timed out. Check that LM Studio is running and serving requests.') from exc
    except urllib.error.URLError as exc:
        code='timeout' if isinstance(exc.reason,(TimeoutError,socket.timeout)) else 'unreachable'
        raise ConnectionFailure(code,'Cannot reach the local server. Start the LM Studio server and check its port.') from exc
    except (UnicodeDecodeError,json.JSONDecodeError) as exc:
        raise ConnectionFailure('invalid_response','The local server returned malformed JSON.') from exc


def test_inference(endpoint,model,timeout=30):
    discovery=discover_models(endpoint)
    if model not in discovery['models']:
        raise ConnectionFailure('model_missing','The selected model is not listed by the local server. Refresh models and select an available identifier.',discovery)
    client=LMStudioClient(endpoint,model,temperature=0,timeout_seconds=timeout)
    started=time.monotonic()
    try:
        reply=client.chat('This is a local connection test. Reply briefly without using tools.','Reply with OK.',max_tokens=8)
    except LMStudioError as exc:
        code='inference_timeout' if exc.code=='timeout' else 'inference_failed'
        message=(f'The model did not answer within {timeout} seconds. It may still be loading. Load it manually in LM Studio, inspect its Server Logs, then retry or increase the saved timeout.' if code=='inference_timeout' else f'The server lists this model, but inference failed: {exc}. Check LM Studio Server Logs for a loading or engine error.')
        raise ConnectionFailure(code,message,discovery) from exc
    if not reply.strip():
        raise ConnectionFailure('invalid_response','The selected model returned an empty reply.',discovery)
    return dict(discovery,inference_ms=round((time.monotonic()-started)*1000),reply=reply[:200],checked_at=datetime.now(timezone.utc).isoformat())
