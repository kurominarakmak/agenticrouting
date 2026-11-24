"""Check visible final answers; reasoning text is never acceptance evidence."""
import re

def final_answer(text):
    if '</think>' in text:return text.rsplit('</think>',1)[-1].strip()
    return '' if '<think>' in text else text.strip()

def grounded_answer(text,expected,hashes):
    text=final_answer(text)
    return bool(re.search(r'(?<![\w.])'+re.escape(expected)+r'(?![\w.])',text.replace(',',''))) and all(h in text for h in hashes)
