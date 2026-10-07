"""Načítání textů panelů z adresáře texts/.

Formát souboru: první řádek ``# Nadpis``, zbytek je text zprávy (Discord markdown).
Komentáře ``<!-- ... -->`` se nezobrazují – hodí se na poznámky pro tebe.

Zástupné značky:
  {server}     název serveru
  {#cenik}     odkaz na kanál podle klíče z layout.py
  {@premium}   zmínka role podle klíče z layout.py
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

TEXTS_DIR = Path(__file__).resolve().parent.parent / "texts"
PLACEHOLDER = re.compile(r"\{([#@])([a-z0-9_]+)\}")
COMMENT = re.compile(r"<!--.*?-->\n?", re.DOTALL)
UNFILLED = "XXX"  # značka nevyplněné hodnoty (např. ceny)


@dataclass(frozen=True)
class Text:
    title: str
    body: str


def load_text(key: str, directory: Path = TEXTS_DIR) -> Text:
    raw = COMMENT.sub("", (directory / f"{key}.md").read_text(encoding="utf-8")).strip()
    first, _, rest = raw.partition("\n")
    if not first.startswith("# "):
        raise ValueError(f"texts/{key}.md musí začínat řádkem '# Nadpis'")
    return Text(title=first[2:].strip(), body=rest.strip())


def placeholders(template: str) -> list[tuple[str, str]]:
    return PLACEHOLDER.findall(template)


def render(
    template: str,
    *,
    server: str,
    channel: Callable[[str], str],
    role: Callable[[str], str],
) -> str:
    template = template.replace("{server}", server)
    return PLACEHOLDER.sub(lambda m: channel(m[2]) if m[1] == "#" else role(m[2]), template)
