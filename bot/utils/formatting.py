import html


def escape_html(text: str | None) -> str:
    if not text:
        return ""
    return html.escape(text, quote=False)
