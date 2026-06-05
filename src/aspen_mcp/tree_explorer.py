"""Tree helpers — thread-safe IHNode enumeration via path strings.

All functions in this module accept a *path* (backslash-delimited string
or parts list) and a *root* node from which to navigate.  They are
designed to be called ONLY from inside an aspen.call() lambda (i.e.
on the COM apartment thread).

Typical usage inside a tool function:

    def impl():
        root = aspen._app.RootModel("")
        names = list_children_names(root, "Data", "Blocks")
        # ...
    return aspen.call(impl)

Note: These helpers operate on COM nodes directly and MUST run on the
COM apartment thread.  Do NOT import them at module level and call
them from the calling thread.
"""

from __future__ import annotations

from typing import Any


def _walk(root: Any, *parts: str) -> Any | None:
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


def list_children_names(root: Any, *parts: str) -> list[str]:
    """Return the .Name of every child at *path* under *root*."""
    node = _walk(root, *parts) if parts else root
    if node is None:
        return []
    names: list[str] = []
    for i in range(10_000):
        try:
            child = node.Elements(i)
        except Exception:
            break
        if child is None:
            break
        names.append(child.Name)
    return names


def node_info(root: Any, *parts: str,
              depth_limit: int = 1) -> dict[str, Any]:
    """Convert an IHNode and its children to a plain dict.

    Args:
        root: Root IHNode (e.g. from aspen._app.RootModel("")).
        parts: Path segments. Empty = use root itself.
        depth_limit: How deep to recurse (0 = just this node).
    """
    node = _walk(root, *parts) if parts else root
    if node is None:
        return {"error": "node not found"}

    info: dict[str, Any] = {"name": node.Name}
    try:
        if node.ValueType != 0:
            info["value"] = node.Value
            try:
                info["unit"] = node.UnitString
            except Exception:
                pass
    except Exception:
        pass

    if depth_limit > 0:
        children = []
        for i in range(10_000):
            try:
                child = node.Elements(i)
            except Exception:
                break
            if child is None:
                break
            try:
                sub_parts = list(parts) + [str(i)] if parts else [str(i)]
                children.append(node_info(root, *sub_parts,
                                          depth_limit=depth_limit - 1))
            except Exception:
                children.append({"name": f"?_{i}"})
        if children:
            info["children"] = children

    return info


def enumerate_values(root: Any, *parts: str,
                     max_keys: int = 80) -> dict[str, Any]:
    """Return {Name: Value} for every scalar child at *path*."""
    node = _walk(root, *parts) if parts else root
    if node is None:
        return {}
    data: dict[str, Any] = {}
    seen = 0
    for i in range(10_000):
        try:
            c = node.Elements(i)
        except Exception:
            break
        if c is None:
            break
        if c.ValueType == 0:
            continue
        data[c.Name] = c.Value
        seen += 1
        if seen >= max_keys:
            break
    return data
