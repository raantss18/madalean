"""Interface language. French is the source language: `_("texte")` returns the English catalogue entry when the
interface is in English. Templates with placeholders use str.format: `_("Essai {i}/{n}").format(i=1, n=8)`."""
from __future__ import annotations

LANGS = {"fr": "Français", "en": "English"}
_lang = "fr"


def set_language(code: str) -> None:
    global _lang
    _lang = code if code in LANGS else "fr"


def language() -> str:
    return _lang


def _(text: str) -> str:
    if _lang == "fr":
        return text
    from .i18n_en import EN
    return EN.get(text, text)


def pick(fr: str, en: str) -> str:
    """For long texts kept side by side (help page, model prompts)."""
    return en if _lang == "en" else fr


def msg(key: str, **params) -> dict:
    """Message for the API: the French source template is the key (same convention as `_`), plus the text in the
    current interface language. Clients may re-localize from `key` + `params`."""
    text = _(key)
    if params:
        try:
            text = text.format(**params)
        except (KeyError, IndexError, ValueError):
            pass
    return {"key": key, "params": params, "text": text}
