"""Every French string of the server has an English translation with the same placeholders; API messages follow
the `language` setting."""
import importlib.util
import re
from pathlib import Path

from madalean import i18n
from madalean.i18n_en import EN

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("mkeys", ROOT / "scripts" / "dev" / "madalean_i18n_keys.py")
keys_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(keys_mod)


def test_every_server_string_is_translated():
    missing = sorted(keys_mod.keys() - set(EN))
    assert not missing, f"{len(missing)} untranslated: {missing[:10]}"


def test_placeholders_match():
    bad = [k for k, v in EN.items() if sorted(re.findall(r"\{[^}]*\}", k)) != sorted(re.findall(r"\{[^}]*\}", v))]
    assert not bad, bad


def test_no_french_left_in_english_catalogue():
    french = re.compile(r"[éèàùçêâîôû]|(?<!\\)\b(le|la|les|une|des|est|pas|vous|votre|avec|pour)\b", re.I)
    allowed = {"Goedel-Formalizer", "mradermacher"}
    bad = [v for v in EN.values() if french.search(v) and not any(a in v for a in allowed)]
    assert not bad, bad[:10]


def test_msg_carries_key_params_and_localized_text():
    try:
        i18n.set_language("en")
        m = i18n.msg("Lean a trouvé {n} erreurs.", n=3)
        assert m == {"key": "Lean a trouvé {n} erreurs.", "params": {"n": 3}, "text": "Lean found 3 errors."}
        i18n.set_language("fr")
        assert i18n.msg("Lean a trouvé {n} erreurs.", n=3)["text"] == "Lean a trouvé 3 erreurs."
        i18n.set_language("xx")
        assert i18n.language() == "fr"
    finally:
        i18n.set_language("fr")
