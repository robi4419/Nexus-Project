"""Turn job-description HTML into readable plain text."""

import html
import re

_LIST_ITEM = re.compile(r"<\s*li\b[^>]*>", re.IGNORECASE)  # opening <li> only; </li> becomes a space below
_BLOCK_TAG = re.compile(
    r"<\s*/?\s*(?:p|div|br|ul|ol|h[1-6]|tr|table|section|article|blockquote)\b[^>]*>", re.IGNORECASE
)
_ANY_TAG = re.compile(r"<[^>]*>")
# Escaped closing tags and line breaks: markup sent escaped once more, not text that shows a tag
_ESCAPED_MARKUP = re.compile(
    r"&lt;\s*/\s*(?:p|div|li|ul|ol|h[1-6]|span|strong|b|em|i|a|table|tr|td)\s*&gt;|&lt;\s*br\s*/?\s*&gt;",
    re.IGNORECASE,
)
_SPACES = re.compile(r"[ \t\r\f\v ]+")
_EXTRA_BLANK_LINES = re.compile(r"\n{3,}")


def html_to_text(html_text: str | None) -> str | None:
    """Return the text of an HTML fragment: block elements become line breaks, list items become "- " lines."""
    if html_text is None:
        return None
    text = html_text
    # Some Arbeitnow postings carry the employer's HTML escaped once more ("&lt;p&gt;...&lt;/p&gt;", with Arbeitnow's own
    # footer in plain HTML): that layer is unescaped first, so its tags become markup instead of visible text.
    if _ESCAPED_MARKUP.search(text):
        text = html.unescape(text)
    text = _LIST_ITEM.sub("\n- ", text)
    text = _BLOCK_TAG.sub("\n", text)
    text = _ANY_TAG.sub(" ", text)
    text = html.unescape(text)  # after removing tags, so an escaped "&lt;div&gt;" stays visible text
    text = _SPACES.sub(" ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    return _EXTRA_BLANK_LINES.sub("\n\n", text).strip()
