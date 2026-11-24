"""Provider-neutral, no-tools inference adapters with explicit owner budgets."""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

SUPPORTED = {"ollama", "lmstudio", "openai-compatible", "openai", "anthropic"}
NAME = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())


def _settings():
    import services
    try:
        value = services.orchestration_settings()
    except __import__('sqlite3').Error:
        # A routing-only caller may exist before app setup, or after a disposable
        # test state has been removed. Configured file settings remain available.
        return {}
    return value if isinstance(value, dict) else {}


def _local_url(url):
    parsed = urllib.parse.urlsplit(url)
    return parsed.hostname in {"127.0.0.1", "localhost", "::1"}


def validate_provider(provider_id, spec):
    if not isinstance(provider_id, str) or not NAME.fullmatch(provider_id) or not isinstance(spec, dict):
        raise ValueError("Provider identity or configuration is invalid")
    allowed={"type","base_url","label","enabled","remote","share_context","metered","consent","budget_calls","task_call_limit",
             "max_output_tokens","timeout_seconds","secret_ref","models","structured_output","capabilities","harnesses","api_version",
             "reasoning_efforts_by_model","reasoning_parameter","temperature","top_p"}
    if set(spec)-allowed:raise ValueError("Provider configuration contains unsupported fields")
    kind = spec.get("type")
    if kind not in SUPPORTED:
        raise ValueError("Provider type must be a supported explicit adapter")
    base = spec.get("base_url")
    if not isinstance(base, str) or len(base) > 500:
        raise ValueError("Provider base URL is required")
    parsed = urllib.parse.urlsplit(base)
    if parsed.scheme not in ("https", "http") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Provider URL must be HTTPS or loopback HTTP without embedded credentials")
    endpoint_remote = not _local_url(base)
    declared_remote = spec.get("remote", False)
    if endpoint_remote and not declared_remote:
        raise ValueError("Non-loopback provider endpoints must be explicitly configured as remote")
    remote = endpoint_remote or declared_remote
    if parsed.scheme == "http" and not _local_url(base):
        raise ValueError("Remote providers require HTTPS")
    if kind in {"ollama", "lmstudio"} and not _local_url(base):
        raise ValueError("Local providers must use a loopback endpoint")
    if kind == "anthropic" and parsed.scheme != "https" and not _local_url(base):
        raise ValueError("Anthropic-compatible remote endpoints require HTTPS")
    for key in ("api_key", "token", "secret", "authorization"):
        if key in spec:
            raise ValueError("Provider secrets must use owner-only secret references, never settings values")
    secret_ref = spec.get("secret_ref")
    if secret_ref is not None and (not isinstance(secret_ref, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}#[A-Za-z0-9_.-]{1,100}", secret_ref)):
        raise ValueError("Secret reference must be an owner-only file and key name")
    for flag in ("enabled", "remote", "share_context", "metered", "consent"):
        if flag in spec and not isinstance(spec[flag], bool):
            raise ValueError("Provider policy flags must be boolean")
    if "structured_output" in spec and not isinstance(spec["structured_output"], bool):
        raise ValueError("Structured-output support must be explicitly configured")
    if "timeout_seconds" in spec and (type(spec["timeout_seconds"]) is not int or not 1<=spec["timeout_seconds"]<=120):
        raise ValueError("Provider timeout must be between 1 and 120 seconds")
    for field in ("capabilities", "harnesses"):
        value = spec.get(field, [])
        if not isinstance(value, list) or len(value) > 30 or any(not isinstance(x, str) or len(x) > 100 for x in value):
            raise ValueError("Provider capability declarations must be bounded explicit lists")
    reasoning=spec.get("reasoning_efforts_by_model",{})
    if not isinstance(reasoning,dict) or len(reasoning)>100 or any(not isinstance(m,str) or not isinstance(vals,list) or len(vals)>10 or any(not isinstance(x,str) or len(x)>32 for x in vals) for m,vals in reasoning.items()):
        raise ValueError("Reasoning support must be declared by exact model ID")
    parameter=spec.get("reasoning_parameter")
    if parameter is not None and (kind!="openai-compatible" or parameter!="reasoning_effort"):
        raise ValueError("OpenAI-compatible reasoning parameters must be explicitly declared")
    if "api_version" in spec and (not isinstance(spec["api_version"],str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,40}",spec["api_version"])):
        raise ValueError("Provider API version is invalid")
    for key,low,high in (("temperature",0.0,2.0),("top_p",0.0,1.0)):
        value=spec.get(key)
        if value is not None and (type(value) not in (int,float) or not low<=value<=high):
            raise ValueError("Provider sampling controls must be finite values within supported bounds")
    models = spec.get("models", [])
    if not isinstance(models, list) or len(models) > 100 or any(not isinstance(m, str) or not 1 <= len(m) <= 200 for m in models):
        raise ValueError("Models must be exact configured model identifiers")
    if remote:
        if not spec.get("enabled") or not spec.get("share_context"):
            raise ValueError("Remote providers require enabled status and explicit context-sharing consent")
        if spec.get("metered") and not spec.get("consent"):
            raise ValueError("Metered providers require explicit spend consent")
        for field in ("budget_calls", "task_call_limit", "max_output_tokens"):
            if type(spec.get(field)) is not int or spec[field] < 1:
                raise ValueError("Remote providers require finite call and output-token budgets")
    else:
        # Local calls also receive finite output and task limits. A missing global call budget
        # is allowed only for local compute; the task cap still bounds repeated requests.
        if type(spec.get("max_output_tokens", 1200)) is not int or not 1 <= spec.get("max_output_tokens", 1200) <= 8192:
            raise ValueError("Output token cap must be between 1 and 8192")
        if type(spec.get("task_call_limit", 8)) is not int or not 1 <= spec.get("task_call_limit", 8) <= 100:
            raise ValueError("Task call limit must be finite")
    normalized = dict(spec)
    normalized["remote"] = remote
    return normalized


def registry():
    import services
    app = services.A
    result = {k: dict(v) for k, v in (app.CONFIG.get("providers", {}) or {}).items() if isinstance(v, dict)}
    persisted = _settings().get("providers", {})
    if isinstance(persisted, dict):
        result.update({k: dict(v) for k, v in persisted.items() if isinstance(v, dict)})
    # Backward-compatible local default uses the configured exact Ollama model, not an
    # architecture-level model choice. It never makes a remote call.
    if "ollama" not in result and app.CONFIG.get("local_model"):
        model = app.CONFIG["local_model"]
        kind = "lmstudio" if str(model).startswith("lmstudio:") else "ollama"
        base = "http://127.0.0.1:1234/v1" if kind == "lmstudio" else "http://127.0.0.1:11434"
        model = str(model).split(":", 1)[1] if str(model).startswith(("ollama:", "lmstudio:")) else model
        result["ollama"] = {"type": kind, "base_url": base, "enabled": True, "remote": False,
                            "models": [model], "task_call_limit": 8, "max_output_tokens": 1200}
    checked = {}
    for key, value in result.items():
        checked[key] = validate_provider(key, value)
    return checked


def role_config(role):
    orchestration = _settings()
    configured = orchestration.get("roles", {})
    spec = configured.get(role, {}) if isinstance(configured, dict) else {}
    if spec:
        return dict(spec)
    import services
    spec = (services.A.CONFIG.get("roles", {}) or {}).get(role, {})
    return dict(spec) if isinstance(spec, dict) else {}


def _provider_secret(spec):
    ref = spec.get("secret_ref")
    if not ref:
        if spec.get("remote") and spec.get("type") in {"openai", "openai-compatible", "anthropic"}:
            raise ValueError("Remote provider needs an owner-only secret reference")
        return None
    filename, key = ref.split("#", 1)
    import services
    secret = services.credential_values(filename).get(key)
    if not secret:
        raise ValueError("Configured provider secret reference is missing")
    return secret


def _join(base, suffix):
    return base.rstrip("/") + "/" + suffix.lstrip("/")


def discover(force=False):
    """Return configured/discovered exact model IDs. No unconfigured integrations are claimed."""
    rows = []
    for provider_id, spec in registry().items():
        kind = spec["type"]
        listed, status, probe_failed = [], "configured; availability not probed", False
        if spec.get("remote"):
            if not spec.get("secret_ref"):
                authentication='missing owner-only secret reference'
            else:
                try:_provider_secret(spec);authentication='owner-only secret file readable; provider auth not verified'
                except (OSError,ValueError):authentication='secret reference missing or refused'
        else:authentication='not required for local loopback'
        if spec.get("enabled") and force:
            try:
                if spec.get("remote") and authentication!='owner-only secret file readable; provider auth not verified':
                    raise ValueError('Provider secret reference unavailable')
                if kind == "ollama":
                    data = _request(_join(spec["base_url"], "/api/tags"), None, None, timeout=3)
                    listed = [x.get("name") for x in data.get("models", []) if isinstance(x, dict) and isinstance(x.get("name"), str)]
                elif kind in {"lmstudio", "openai-compatible", "openai"}:
                    data = _request(_join(spec["base_url"], "/models"), None, _provider_secret(spec), timeout=3)
                    listed = [x.get("id") for x in data.get("data", []) if isinstance(x, dict) and isinstance(x.get("id"), str)]
                status = "model listing observed" if listed else "endpoint responded; no model identifiers returned"
            except (OSError, ValueError, urllib.error.URLError):
                status = "model discovery failed; availability is unverified"
                probe_failed = True
        configured = spec.get("models", [])
        models = list(dict.fromkeys(listed + configured))
        rows.append({"id": provider_id, "name": spec.get("label", provider_id), "provider": provider_id,
                     "provider_type": kind, "base_url": spec["base_url"], "remote": bool(spec.get("remote")),
                     "enabled": bool(spec.get("enabled")), "available": True if listed else (False if probe_failed else None), "discovery": status,
                     "availability": "observed" if listed else ("unavailable" if probe_failed else "unknown"),
                     "models": [{"id": m, "source": "endpoint" if m in listed else "configuration"} for m in models],
                     "authentication": authentication,
                     "billing": "metered API; finite request budget" if spec.get("metered") else ("remote billing unknown" if spec.get("remote") else "local compute"),
                     "capabilities": list(spec.get("capabilities", [])), "harnesses": list(spec.get("harnesses", [])),
                     "budget_calls": spec.get("budget_calls") if spec.get("remote") else None,
                     "task_call_limit": spec.get("task_call_limit", 8), "quota": "not reported"})
    return rows


def _request(url, payload, secret, timeout):
    headers = {"Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if secret:
        headers["Authorization"] = "Bearer " + secret
    request = urllib.request.Request(url, json.dumps(payload).encode() if payload is not None else None, headers)
    try:
        opener = _opener()
        with opener.open(request, timeout=timeout) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError("Provider response exceeded the configured size limit")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("Provider returned an invalid response")
        return data
    except urllib.error.HTTPError as exc:
        # Do not surface provider response bodies; some services echo request credentials.
        raise ValueError("Provider request failed with HTTP status %d" % exc.code) from None


def _request_headers(url, payload, headers, timeout):
    request = urllib.request.Request(url, json.dumps(payload).encode(),
                                     {"Content-Type": "application/json", "Accept": "application/json", **headers})
    try:
        with _opener().open(request, timeout=timeout) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError("Provider response exceeded the configured size limit")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("Provider returned an invalid response")
        return data
    except urllib.error.HTTPError as exc:
        raise ValueError("Provider request failed with HTTP status %d" % exc.code) from None


def complete(provider_id, model, messages, schema=None, *, role="assistant", task_id=None,
             share_context=False, on_delta=None, deadline=None):
    """One bounded inference request. This adapter has no tool or shell execution path."""
    import control
    spec = registry().get(provider_id)
    if not spec or not spec.get("enabled"):
        raise ValueError("Provider is not configured and enabled")
    if provider_id in _settings().get("excluded_providers", []):
        raise ValueError("Configured provider is excluded by owner policy")
    declared_models = spec.get("models", [])
    configured_role = role_config(role)
    if (not isinstance(model, str) or not model or
            (declared_models and model not in declared_models) or
            (not declared_models and not (configured_role.get("provider") == provider_id and configured_role.get("model") == model))):
        raise ValueError("Model ID must be present in the provider's exact configured model list")
    if spec.get("remote") and (not spec.get("share_context") or not share_context):
        raise ValueError("Private context is not authorized for this remote provider")
    if spec.get("remote") and spec.get("metered") and not spec.get("consent"):
        raise ValueError("Metered API usage lacks explicit owner consent")
    if not isinstance(messages, list) or len(messages) > 24 or sum(len(str(m.get("content", ""))) for m in messages if isinstance(m, dict)) > 50000:
        raise ValueError("Provider context exceeds the bounded input size")
    role_spec=role_config(role);effort=role_spec.get("reasoning_effort")
    declared_efforts=spec.get("reasoning_efforts_by_model",{}).get(model,[])
    if effort and effort not in declared_efforts:raise ValueError("Reasoning effort is not declared for this provider model")
    limit = spec.get("max_output_tokens", 1200)
    control.reserve_provider_call(provider_id, model, role, task_id, limit,
                                  spec.get("budget_calls") if spec.get("remote") else None,
                                  spec.get("task_call_limit", 8))
    secret = _provider_secret(spec)
    kind, base = spec["type"], spec["base_url"]
    timeout = min(120, max(1, float(spec.get("timeout_seconds", 90))))
    if deadline is not None:
        timeout=min(timeout,deadline-time.monotonic())
        if timeout<=0:raise TimeoutError("Configured orchestration wall-clock budget exhausted before provider request")
    started = time.monotonic()
    if kind == "ollama":
        body = {"model": model, "messages": messages, "stream": False,
                "options": {"temperature": spec.get("temperature",0), "num_predict": limit}, "think": False}
        if "top_p" in spec:body["options"]["top_p"]=spec["top_p"]
        if schema:
            body["format"] = schema
        data = _request(_join(base, "/api/chat"), body, None, timeout)
        text = str(data.get("message", {}).get("content", ""))
        usage = {"input_tokens": data.get("prompt_eval_count"), "output_tokens": data.get("eval_count")}
    elif kind in {"lmstudio", "openai-compatible"}:
        body = {"model": model, "messages": messages, "stream": False,
                "temperature": spec.get("temperature",0), "max_tokens": limit}
        if "top_p" in spec:body["top_p"]=spec["top_p"]
        if effort:
            if spec.get("reasoning_parameter")!="reasoning_effort":raise ValueError("Reasoning parameter is not declared for this compatible endpoint")
            body["reasoning_effort"]=effort
        if schema and spec.get("structured_output") is True:
            body["response_format"] = {"type": "json_schema", "json_schema": {"name": "decision", "strict": True, "schema": schema}}
        data = _request(_join(base, "/chat/completions"), body, secret, timeout)
        text = str(data.get("choices", [{}])[0].get("message", {}).get("content", ""))
        usage = {"input_tokens": data.get("usage", {}).get("prompt_tokens"), "output_tokens": data.get("usage", {}).get("completion_tokens")}
    elif kind == "openai":
        body = {"model": model, "input": messages, "max_output_tokens": limit, "store": False}
        if effort:body["reasoning"]={"effort":effort}
        if schema and spec.get("structured_output") is True:
            body["text"] = {"format": {"type": "json_schema", "name": "decision", "strict": True, "schema": schema}}
        data = _request(_join(base, "/responses"), body, secret, timeout)
        pieces = []
        for item in data.get("output", []):
            for part in item.get("content", []):
                if part.get("type") in ("output_text", "text"):
                    pieces.append(str(part.get("text", "")))
        text = "\n".join(pieces)
        usage = {"input_tokens": data.get("usage", {}).get("input_tokens"), "output_tokens": data.get("usage", {}).get("output_tokens")}
    else:  # Anthropic Messages API; API calls are distinct from Claude Code subscription auth.
        system = "\n".join(str(m.get("content", "")) for m in messages if m.get("role") == "system")
        conversation = [{"role": m.get("role"), "content": m.get("content", "")} for m in messages if m.get("role") != "system"]
        body = {"model": model, "max_tokens": limit, "messages": conversation, "temperature": 0}
        if effort:raise ValueError("Anthropic reasoning effort is unsupported by this adapter")
        if system:
            body["system"] = system
        if schema and spec.get("structured_output") is True:
            body["output_config"] = {"format": {"type": "json_schema", "schema": schema}}
        headers = {"x-api-key": secret, "anthropic-version": spec.get("api_version", "2023-06-01")}
        if not secret:
            raise ValueError("Anthropic provider requires an owner-only secret reference")
        data = _request_headers(_join(base, "/messages"), body, headers, timeout)
        text = "\n".join(str(p.get("text", "")) for p in data.get("content", []) if p.get("type") == "text")
        usage = {"input_tokens": data.get("usage", {}).get("input_tokens"), "output_tokens": data.get("usage", {}).get("output_tokens")}
    text = text.strip()
    if not text:
        raise ValueError("Provider returned no text")
    from output_safety import visible_text
    text=visible_text(text)
    if on_delta:
        on_delta(text)
    control.finish_provider_call(provider_id, model, role, task_id, usage)
    return {"text": text, "usage": usage, "elapsed_seconds": round(time.monotonic() - started, 3),
            "provider": provider_id, "model": model, "role": role}
