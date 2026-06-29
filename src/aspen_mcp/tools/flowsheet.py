"""Flowsheet topology and side duty tools.

All COM operations run inside aspen.call() lambdas on the dedicated
COM apartment thread.
"""

from __future__ import annotations

from ..com_bridge import aspen
from ._common import walk


def tool_flowsheet_topology() -> str:
    """Show flowsheet topology: SOURCE --[stream]--> DEST.

    Returns a text diagram of all block connections.
    """
    try:
        def impl():
            tree = aspen._app.RootModel("")
            lines = ["Flowsheet Topology:"]

            blocks_node = walk(tree, "Data", "Blocks")
            if blocks_node is None:
                return "Flowsheet is empty (no blocks)"
            
            # Build topology from block ports
            # For each block's output ports, trace connected streams to destination blocks
            connections: list[tuple[str, str, str]] = []  # (src_block, stream, dst_block)
            seen_streams: set[str] = set()
            
            for bi in range(200):
                try:
                    block = blocks_node.Elements(bi)
                except Exception:
                    break
                if block is None:
                    break
                block_name = block.Name
                
                try:
                    ports_node = block.Elements("Ports")
                except Exception:
                    continue
                
                for pi in range(30):
                    try:
                        port = ports_node.Elements(pi)
                    except Exception:
                        break
                    if port is None:
                        break
                    
                    port_name = port.Name
                    # Only show OUTPUT ports as sources
                    if "(OUT)" not in port_name and port_name not in ("P(OUT)",):
                        continue
                    
                    try:
                        port_els = port.Elements
                    except Exception:
                        continue
                    
                    for k in range(port_els.Count):
                        try:
                            stream_name = port_els.Item(k).Name
                        except Exception:
                            break
                        
                        if stream_name in seen_streams:
                            continue
                        seen_streams.add(stream_name)
                        
                        # Find which block's INPUT has this stream
                        dst_block = "?"
                        for bj in range(200):
                            try:
                                other_block = blocks_node.Elements(bj)
                            except Exception:
                                break
                            if other_block is None:
                                break
                            if other_block.Name == block_name:
                                continue
                            try:
                                other_ports = other_block.Elements("Ports")
                            except Exception:
                                continue
                            for pj in range(30):
                                try:
                                    other_port = other_ports.Elements(pj)
                                except Exception:
                                    break
                                if other_port is None:
                                    break
                                if "(IN)" in other_port.Name or other_port.Name == "F(IN)":
                                    try:
                                        other_els = other_port.Elements
                                    except Exception:
                                        continue
                                    for kj in range(other_els.Count):
                                        try:
                                            if other_els.Item(kj).Name == stream_name:
                                                dst_block = other_block.Name
                                                break
                                        except Exception:
                                            break
                                    if dst_block != "?":
                                        break
                            if dst_block != "?":
                                break
                        
                        # No downstream consumer = product stream
                        if dst_block == "?":
                            dst_block = "(product)"
                        connections.append((block_name, stream_name, dst_block))

            # Also show feed streams (connected to block inputs, no upstream block)
            for bi in range(200):
                try:
                    block = blocks_node.Elements(bi)
                except Exception:
                    break
                if block is None:
                    break
                block_name2 = block.Name
                try:
                    ports_node2 = block.Elements("Ports")
                except Exception:
                    continue
                for pi in range(30):
                    try:
                        port2 = ports_node2.Elements(pi)
                    except Exception:
                        break
                    if port2 is None:
                        break
                    port_name2 = port2.Name
                    if "(IN)" not in port_name2 and port_name2 != "F(IN)":
                        continue
                    try:
                        port_els2 = port2.Elements
                    except Exception:
                        continue
                    for k in range(port_els2.Count):
                        try:
                            sname2 = port_els2.Item(k).Name
                        except Exception:
                            break
                        if sname2 in seen_streams:
                            continue
                        seen_streams.add(sname2)
                        connections.append(("(feed)", sname2, block_name2))
            
            if not connections:
                # Fallback: try SOURCE/DESTINATION from stream Output (requires run)
                streams_node = walk(tree, "Data", "Streams")
                if streams_node is not None:
                    for i in range(200):
                        try:
                            s = streams_node.Elements(i)
                        except Exception:
                            break
                        if s is None:
                            break
                        sname = s.Name
                        src = walk(tree, "Data", "Streams", sname, "Output", "SOURCE")
                        dst = walk(tree, "Data", "Streams", sname, "Output", "DESTINATION")
                        src_val = src.Value if src is not None else None
                        dst_val = dst.Value if dst is not None else None
                        if src_val or dst_val:
                            connections.append((str(src_val or "?"), sname, str(dst_val or "?")))
            
            if not connections:
                return "Flowsheet is empty (no connections found)"
            
            for src, stream, dst in connections:
                lines.append(f"  {src} --[{stream}]--> {dst}")
            
            return "\n".join(lines)
        return aspen.call(impl)
    except Exception as exc:
        return f"Error: {exc}"


def tool_add_side_duty(block_name: str, stage: int, duty: float) -> str:
    """Add/update a side heater/cooler duty on a RadFrac stage."""
    try:
        def impl():
            tree = aspen._app.RootModel("")
            # Navigate to side duties under RadFrac block
            # Path: Data\Blocks\{name}\Input\SIDE_DUTIES\{stage name}\DUTY
            path = walk(tree, "Data", "Blocks", block_name, "Input")
            if path is None:
                return f"Block '{block_name}' Input not found"
            sd_node = walk(tree, "Data", "Blocks", block_name, "Input", "SIDE_DUTIES")
            if sd_node is None:
                return f"No SIDE_DUTIES on block '{block_name}' (is it RadFrac?)"
            # Find or create the stage entry
            stage_name = None
            for i in range(100):
                try:
                    c = sd_node.Elements(i)
                except Exception:
                    break
                if c is None:
                    break
                if c.Name.endswith(str(stage)):
                    stage_name = c.Name
                    break
            if stage_name is None:
                return f"Stage {stage} not found in SIDE_DUTIES"
            duty_node = walk(tree, "Data", "Blocks", block_name, "Input",
                              "SIDE_DUTIES", stage_name, "DUTY")
            if duty_node is None:
                return f"DUTY node not found for stage {stage}"
            duty_node.SetValue(0, duty)
            return f"Side duty set on {block_name} stage {stage} = {duty}"
        return aspen.call(impl)
    except Exception as exc:
        return f"Error: {exc}"


def tool_remove_side_duty(block_name: str, stage: int) -> str:
    """Remove a side duty from a RadFrac stage."""
    try:
        def impl():
            tree = aspen._app.RootModel("")
            sd_node = walk(tree, "Data", "Blocks", block_name, "Input", "SIDE_DUTIES")
            if sd_node is None:
                return f"No SIDE_DUTIES on block '{block_name}'"
            target_idx = None
            for i in range(100):
                try:
                    c = sd_node.Elements(i)
                except Exception:
                    break
                if c is None:
                    break
                if c.Name.endswith(str(stage)):
                    target_idx = i
                    break
            if target_idx is None:
                return f"Stage {stage} not found in SIDE_DUTIES"
            sd_node.Elements.RemoveRow(0, target_idx)
            return f"Side duty removed from {block_name} stage {stage}"
        return aspen.call(impl)
    except Exception as exc:
        return f"Error: {exc}"


def tool_configure_fsplit(block_name: str, outlet_name: str, frac: float) -> str:
    """Add/configure a second product outlet on an FSPLIT block.

    Sets the split fraction for a product outlet. The outlet must
    already exist (use connect_port to connect the stream first).

    Args:
        block_name: FSPLIT block name (e.g. S-1).
        outlet_name: Product stream name (e.g. RECYCLE).
        frac: Split fraction (0.0-1.0) for this outlet; the remainder
              goes to the first outlet automatically.

    Example:
        connect_port("S-1", "P(OUT)", "RECYCLE")
        configure_fsplit("S-1", "RECYCLE", 0.85)
    """
    try:
        def _impl():
            _tree = aspen._app.RootModel("")
            _fp = "\\Data\\Blocks\\" + block_name + "\\Input\\FRAC"
            _frac_node = _tree.FindNode(_fp)
            if _frac_node is None:
                return "FRAC node not found for '" + block_name + "'"
            _frac_els = _frac_node.Elements
            _found = False
            for _i in range(_frac_els.Count):
                try:
                    if _frac_els.Item(_i).Name == outlet_name:
                        _found = True
                        _frac_els.Item(_i).SetValue(0, frac)
                        break
                except Exception:
                    pass
            if not _found:
                return ("Outlet '" + outlet_name + "' not found in FRAC table. "
                        "Connect the stream first with connect_port().")
            return ("FSPLIT '" + block_name + "' outlet '" + outlet_name +
                    "' FRAC=" + str(frac) + ". " + outlet_name + " gets " +
                    str(int(frac*100)) + "% of the inlet flow.")
        return aspen.call(_impl)
    except Exception as _exc:
        return "Error: " + str(_exc)