import re
from typing import Optional

from selectolax.parser import Node


def text_of(node: Optional[Node], default: str = "") -> str:
    return node.text(strip=True) if node is not None else default


def first_text(parent: Node, selector: str, default: str = "") -> str:
    return text_of(parent.css_first(selector), default)


def id_from_href(href: str) -> Optional[str]:
    """vlr hrefs look like /310/sentinels, /event/2498/..., /player/4164/aspas.
    Return the first all-numeric path segment."""
    for seg in href.strip("/").split("/"):
        if seg.isdigit():
            return seg
    return None


def clean_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def country_from_flag(flag: Optional[Node]) -> Optional[str]:
    """vlr flags carry the ISO code as a `mod-xx` class, e.g. `flag mod-ca`."""
    if flag is None:
        return None
    for cls in (flag.attributes.get("class", "") or "").split():
        if cls.startswith("mod-"):
            return cls[len("mod-") :] or None
    return None
