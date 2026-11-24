"""Remove private reasoning tags before any model text crosses an app boundary."""
import re
import json


def visible_text(value):
    if not isinstance(value, str):
        raise ValueError("Model returned an invalid text response")
    # Remove complete tagged reasoning segments, including multiple interleaved blocks.
    text=re.sub(r"<think\b[^>]*>.*?</think\s*>","",value,flags=re.I|re.S)
    # A dangling opening tag means the response ended inside reasoning. Keep only text before
    # that tag; never surface the unfinished private segment as a fallback answer.
    text=re.split(r"<think\b[^>]*>",text,flags=re.I,maxsplit=1)[0]
    # Some compatible endpoints emit a closing marker without its opening token.
    if re.search(r"</think\s*>",text,re.I):text=re.split(r"</think\s*>",text,flags=re.I)[-1]
    text=re.sub(r"[ \t]+\n","\n",text).strip()
    if not text:
        raise ValueError("Provider returned no visible answer after private reasoning was removed")
    return text


def json_object(value):
    """Parse strict JSON or one exact Markdown JSON fence, with no surrounding prose."""
    if not isinstance(value,str):raise ValueError("Model returned an invalid JSON response")
    text=value.strip()
    if text.startswith("```"):
        match=re.fullmatch(r"```(?:json)?[ \t]*\n(.*?)\n```",text,flags=re.I|re.S)
        if not match:raise ValueError("Model response contains prose or an invalid JSON fence")
        text=match.group(1).strip()
    try:parsed=json.loads(text)
    except (ValueError,TypeError):raise ValueError("Model returned malformed JSON") from None
    if not isinstance(parsed,dict):raise ValueError("Model JSON must be an object")
    return parsed
