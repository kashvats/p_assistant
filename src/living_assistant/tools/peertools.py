from __future__ import annotations

from .base import Tool


def build_peer_tools(peers) -> list[Tool]:
    return [
        Tool(
            "peer_list",
            "List mDNS-discovered Living Assistant peers. Discovery does not imply trust; only explicitly trusted peers may receive delegated work.",
            {"type": "object", "properties": {}},
            lambda: peers.list_peers(),
        ),
        Tool(
            "peer_delegate",
            "Delegate a bounded text/model task to an explicitly trusted, HTTPS Living Assistant peer. The remote peer runs a tool-free specialist only.",
            {
                "type": "object",
                "properties": {
                    "task": {"type": "string"},
                    "role": {"type": "string", "enum": ["general", "coder", "researcher", "planner"], "default": "general"},
                    "context": {"type": "string", "default": ""},
                    "peer_id": {"type": "string"},
                },
                "required": ["task"],
            },
            peers.delegate,
        ),
    ]
