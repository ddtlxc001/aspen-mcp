"""Shared COM navigation helpers for tools modules.

All functions must be called ON the COM thread (i.e. inside aspen.call()).
"""

from __future__ import annotations

from typing import Any


def walk(root: Any, *parts: str) -> Any | None:
    """Navigate an IHNode tree by path segments.

    Safe to call from within an aspen.call() lambda on the COM thread.
    """
    node = root
    for p in parts:
        try:
            node = node.Elements(p)
        except Exception:
            return None
        if node is None:
            return None
    return node

def ensure_parent(tree: Any, *parts: str) -> Any | None:
    """Ensure a path exists, creating intermediate nodes as needed.

    Handles the dummy-node trick for Blocks/Streams containers:
    creating a temporary child forces Aspen to allocate the container node
    when it would otherwise refuse direct .Add().
    """
    node = tree
    for p in parts:
        try:
            n = node.Elements(p)
            if n is None:
                raise Exception("none")
            node = n
        except Exception:
            try:
                node.Elements.Add(p)
                node = node.Elements(p)
            except Exception:
                # Dummy trick for Data-level containers
                name = parts[-1] if len(parts) > 0 else p
                try:
                    if name == "Blocks":
                        node.Elements.Add("_d_!MIXER")
                        node = node.Elements("Blocks")
                        node.Elements.Remove("_d_")
                        return node
                    elif name == "Streams":
                        node.Elements.Add("_d_")
                        node = node.Elements("Streams")
                        node.Elements.Remove("_d_")
                        return node
                except Exception:
                    pass
                return None
    return node


