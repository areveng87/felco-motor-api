"""
Traduccion de textos con DeepL. La clave se lee de la variable de entorno
DEEPL_API_KEY (no se guarda en el codigo).

- Si la clave acaba en ":fx" usa el endpoint gratuito (api-free.deepl.com).
- Si no hay clave o falla la peticion, devuelve el texto original (sin romper).
"""
import os
from typing import List

import requests


def _endpoint():
    key = os.getenv("DEEPL_API_KEY", "").strip()
    if not key:
        return None, None
    base = "https://api-free.deepl.com" if key.endswith(":fx") else "https://api.deepl.com"
    return key, base


def translate_texts(texts: List[str], target: str = "ES", source: str = "EN") -> List[str]:
    """Traduce una lista de textos. Mantiene el orden. Los vacios se dejan igual."""
    texts = list(texts or [])
    idx = [i for i, t in enumerate(texts) if (t or "").strip()]
    if not idx:
        return texts

    key, base = _endpoint()
    if not key:
        return texts

    payload = [("target_lang", target), ("source_lang", source)]
    payload += [("text", texts[i]) for i in idx]

    try:
        resp = requests.post(
            f"{base}/v2/translate",
            headers={"Authorization": f"DeepL-Auth-Key {key}"},
            data=payload,
            timeout=30,
        )
        if resp.status_code != 200:
            print("DeepL error", resp.status_code, resp.text[:200])
            return texts
        translations = resp.json().get("translations", [])
        out = list(texts)
        for pos, tr in zip(idx, translations):
            out[pos] = tr.get("text", texts[pos])
        return out
    except Exception as e:  # noqa: BLE001
        print("DeepL excepcion:", e)
        return texts


def translate_text(text: str, target: str = "ES", source: str = "EN") -> str:
    if not text or not text.strip():
        return text
    return translate_texts([text], target, source)[0]
