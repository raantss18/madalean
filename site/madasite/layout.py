"""Page shell shared by the manual, the install page and the publication template: strict CSP, no inline script or
style, light/dark, skip link, language switch."""
from __future__ import annotations

import html

CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; "
       "connect-src 'self'; base-uri 'none'; form-action 'none'; manifest-src 'self'")

MARK = ('<svg class="mark" viewBox="0 0 1024 1024" aria-hidden="true" focusable="false">'
        '<g fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M512 610 L300 230 M512 610 L724 230" stroke-width="80"/><path d="M370 418 H654" stroke-width="66"/>'
        '<path d="M300 230 l-62 -38 M300 230 l12 -80 M724 230 l62 -38 M724 230 l-12 -80" stroke-width="42"/></g>'
        '<path d="M458 596 C 420 660 404 740 412 836 H612 C 620 740 604 660 566 596 Z" fill="currentColor"/>'
        '<path d="M300 836 H724" stroke="currentColor" stroke-width="42" stroke-linecap="round"/></svg>')

STR = {
    "fr": {
        "skip": "Aller au contenu", "manual": "Manuel", "download": "Installer", "updates": "Mises à jour",
        "search": "Chercher", "theme": "Thème : automatique", "theme_light": "Thème : clair",
        "theme_dark": "Thème : sombre", "lang_name": "Français", "other": "English", "menu": "Pages du manuel",
        "on_page": "Sur cette page", "prev": "Précédent", "next": "Suivant", "source": "Source de cette page",
        "learner": "apprenant", "researcher": "chercheur", "all": "",
        "footer": "Madalean — logiciel libre (Apache-2.0). Ce site n'utilise ni traceur, ni cookie, ni ressource externe.",
        "image_missing": "Capture d'écran à venir", "nojs_search": "La recherche demande JavaScript ; sans lui, utilisez le plan du manuel.",
        "search_label": "Chercher dans le manuel", "search_none": "Aucun résultat.", "search_results": "résultat(s)", "search_hint": "Tapez au moins deux lettres.",
        "nav_main": "Principal", "nav_lang": "Langue",
    },
    "en": {
        "skip": "Skip to content", "manual": "Manual", "download": "Install", "updates": "Updates",
        "search": "Search", "theme": "Theme: automatic", "theme_light": "Theme: light", "theme_dark": "Theme: dark",
        "lang_name": "English", "other": "Français", "menu": "Manual pages", "on_page": "On this page",
        "prev": "Previous", "next": "Next", "source": "Source of this page", "learner": "learner",
        "researcher": "researcher", "all": "",
        "footer": "Madalean — free software (Apache-2.0). This site uses no tracker, no cookie and no external resource.",
        "image_missing": "Screenshot to come", "nojs_search": "Search needs JavaScript; without it, use the manual's table of contents.",
        "search_label": "Search the manual", "search_none": "No result.", "search_results": "result(s)", "search_hint": "Type at least two letters.",
        "nav_main": "Main", "nav_lang": "Language",
    },
}

SECTIONS = {
    "fr": [("start", "Démarrer"), ("use", "Travailler"), ("research", "Recherche"),
           ("settings", "Réglages et sécurité"), ("help", "Aide"), ("reference", "Référence")],
    "en": [("start", "Getting started"), ("use", "Working"), ("research", "Research"),
           ("settings", "Settings and security"), ("help", "Help"), ("reference", "Reference")],
}

E = html.escape


def page(*, lang: str, title: str, body: str, root: str, description: str = "", alt_href: str | None = None,
         active: str = "", extra_css: list[str] | None = None, site_name: str = "Madalean",
         header_nav: bool = True, scripts: bool = True, home: str | None = None,
         footer: str | None = None, nav_html: str = "") -> str:
    """root = relative path to the site root ('../' from /fr/x.html)."""
    s = STR[lang]
    other = "en" if lang == "fr" else "fr"
    css = "".join(f'<link rel="stylesheet" href="{root}{c}">' for c in ["assets/style.css", *(extra_css or [])])
    nav = ""
    if header_nav:
        def item(key: str, href: str) -> str:
            cur = ' aria-current="page"' if key == active else ""
            return f'<li><a href="{href}"{cur}>{E(s[key])}</a></li>'
        nav = (f'<nav class="top-nav" aria-label="{E(s["nav_main"])}"><ul>'
               + item("manual", f"{root}{lang}/index.html") + item("download", f"{root}{lang}/download.html")
               + item("search", f"{root}{lang}/search.html") + "</ul></nav>")
    langsw = ""
    if alt_href:
        langsw = (f'<nav class="lang" aria-label="{E(s["nav_lang"])}"><a href="{E(alt_href)}" hreflang="{other}" '
                  f'lang="{other}">{other.upper()}<span class="sr-only"> ({E(s["other"])})</span></a></nav>')
    theme = (f'<button type="button" class="theme-toggle" id="theme-toggle" hidden '
             f'data-auto="{E(s["theme"])}" data-light="{E(s["theme_light"])}" data-dark="{E(s["theme_dark"])}" '
             f'aria-label="{E(s["theme"])}"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="8.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 3.5a8.5 8.5 0 0 1 0 17z" fill="currentColor"/></svg></button>')
    js = (f'<script src="{root}assets/theme.js"></script><script src="{root}assets/site.js" defer></script>'
          if scripts else "")
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<meta name="referrer" content="no-referrer">
<meta name="color-scheme" content="light dark">
<title>{E(title)}</title>
{f'<meta name="description" content="{E(description)}">' if description else ''}
<link rel="icon" href="{root}assets/icon.svg" type="image/svg+xml">
{css}
{js}
</head>
<body>
<a class="skip" href="#main">{E(s["skip"])}</a>
<header class="site-header">
<a class="brand" href="{home or (root + lang + '/index.html')}">{MARK}<span>{E(site_name)}</span></a>
{nav}{nav_html}
<div class="header-tools">{langsw}{theme}</div>
</header>
{body}
<footer class="site-footer"><p>{footer if footer is not None else E(s["footer"])}</p></footer>
</body>
</html>
"""
