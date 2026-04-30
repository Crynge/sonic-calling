from __future__ import annotations

from xml.sax.saxutils import escape


def build_stream_twiml(stream_url: str, opening_line: str, session_id: str, agent_name: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f"<Say voice=\"Polly.Joanna\">{escape(opening_line)}</Say>"
        "<Connect>"
        f"<Stream url=\"{escape(stream_url)}\">"
        f"<Parameter name=\"session_id\" value=\"{escape(session_id)}\" />"
        f"<Parameter name=\"agent_name\" value=\"{escape(agent_name)}\" />"
        "</Stream>"
        "</Connect>"
        "</Response>"
    )
