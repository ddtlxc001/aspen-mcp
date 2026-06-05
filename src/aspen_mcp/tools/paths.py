"""Path-based tools: get_value, set_value by backslash path.

All COM operations run inside aspen.call() lambdas on the dedicated
COM apartment thread.
"""

from __future__ import annotations

from ..com_bridge import aspen


def tool_get_value(path: str) -> str:
    """Read a value by backslash path (e.g. Data\\Streams\\S1\\Output\\RES_TEMP)."""
    try:
        def impl():
            tree = aspen._app.RootModel("")
            node = tree.FindNode(path)
            if node is None:
                return f"Node not found: {path}"
            return str(node.Value)
        return aspen.call(impl)
    except Exception as exc:
        return f"Error: {exc}"


def tool_set_value(path: str, value: str | float, unit: str | None = None) -> str:
    """Write a value by backslash path.

    Handles parent nodes that have children by trying child matching first.
    """
    try:
        def impl():
            tree = aspen._app.RootModel("")
            node = tree.FindNode(path)
            if node is None:
                return "Error: Path not found"
            # If node has children and value is a string, try matching child
            try:
                _has_kids = node.Elements.Count > 0
            except Exception:
                _has_kids = False
            if _has_kids and isinstance(value, str):
                for i in range(node.Elements.Count):
                    try:
                        child = node.Elements(i)
                        if child.Name.upper() == value.upper():
                            child.SetValue(0, value)
                            return "Set " + path + " -> " + child.Name + " = " + value
                    except Exception:
                        pass
            node.SetValue(0, value)
            return "Set " + path + " = " + str(value)
        result = aspen.call(impl)
        if isinstance(result, str) and result.startswith("Error"):
            return result
        return result
    except Exception as exc:
        return "Error: " + str(exc)

def tool_insert_row(path: str, dimension: int = 0) -> str:
    """Insert a new row in a table-type node.

    Creates a new empty row. After insertion, the row is accessible
    via FindNode using index notation (e.g. \\#0 for first row).

    Args:
        path: Backslash path to the table node.
        dimension: Table dimension (default 0).
    """
    try:
        def impl():
            tree = aspen._app.RootModel("")
            node = tree.FindNode(path)
            if node is None:
                return f"Error: Node not found: {path}"
            els = node.Elements
            idx = els.Count
            els.InsertRow(dimension, idx)
            return f"Inserted row at '{path}' dim={dimension} index={idx}."
        return aspen.call(impl)
    except Exception as exc:
        return f"Error inserting row: {exc}"

