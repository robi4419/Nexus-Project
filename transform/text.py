"""Turn job-description HTML into readable plain text."""

import html
import re

_LIST_ITEM = re.compile(r"<\s*li\b[^>]*>", re.IGNORECASE)  # opening <li> only; </li> becomes a space below
_BLOCK_TAG = re.compile(
    r"<\s*/?\s*(?:p|div|br|ul|ol|h[1-6]|tr|table|section|article|blockquote)\b[^>]*>", re.IGNORECASE
)
_ANY_TAG = re.compile(r"<[^>]*>")
_SPACES = re.compile(r"[ \t\r\f\v ]+")
_EXTRA_BLANK_LINES = re.compile(r"\n{3,}")


def html_to_text(html_text: str | None) -> str | None:
    """Return the text of an HTML fragment: block elements become line breaks, list items become "- " lines."""
    if html_text is None:
        return None
    text = _LIST_ITEM.sub("\n- ", html_text)
    text = _BLOCK_TAG.sub("\n", text)
    text = _ANY_TAG.sub(" ", text)
    text = html.unescape(text)  # after removing tags, so an escaped "&lt;div&gt;" stays visible text
    text = _SPACES.sub(" ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    return _EXTRA_BLANK_LINES.sub("\n\n", text).strip()
