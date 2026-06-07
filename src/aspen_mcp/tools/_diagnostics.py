"""Diagnostic tools: param scanning, block validation, convergence report.

All COM operations run inside aspen.call() lambdas on the dedicated
COM apartment thread.
"""

from __future__ import annotations

from typing import Any

from ..com_bridge import aspen
from ._common import walk
from ._error import mcp_tool


# --- Unit hints for param descriptions ----------------------------------------

_UNIT_HINTS = {
    (22, 4): "\u00b0C", (20, 5): "bar", (20, 10): "kPa",
    (13, 3): "Gcal/hr", (13, 18): "kW",
    (31, 4): "\u00b0C", (49, 3): "kJ/kg-K",
    (75, 5): "bar", (75, 18): "kPa",
    (17, 3): "m", (11, 3): "kg/hr",
}

# --- Smart parameter categorization per block type ---
# For each block type, specify:
#   - mode_param: the param that selects the operating mode (e.g. SPEC_OPT)
#   - mode_map:   {mode_value: [params_required_in_that_mode]}
#   - default_mode: fallback if mode_param has no value yet
#
# To add a new block type: append to _BLOCK_MODES dict below.
# The block type string comes from _get_block_type() which reads blk.Value
# (e.g. "RADFRAC", "HEATX", "VALVE", "MIXER", etc.).

_BLOCK_MODES: dict[str, dict] = {
    "HEATER": {"mode_param": "SPEC_OPT", "default_mode": "TP",
        "mode_map": {"TP": ["TEMP", "PRES"], "TEMP": ["TEMP"], "DUTY": ["DUTY"],
                     "VFRAC": ["VFRAC"], "PRES": ["PRES"]}},
    "V-DRUM1": {"mode_param": "SPEC_OPT", "default_mode": "TP",
        "mode_map": {"TP": ["TEMP", "PRES"], "TEMP": ["TEMP"], "PRES": ["PRES"],
                     "VFRAC": ["VFRAC"], "DUTY": ["DUTY"]}},
    "FLASH2": {"mode_param": "SPEC_OPT", "default_mode": "TP",
        "mode_map": {"TP": ["TEMP", "PRES"], "TEMP": ["TEMP"], "PRES": ["PRES"],
                     "VFRAC": ["VFRAC"], "DUTY": ["DUTY"]}},
    "ICON2": {"mode_param": "SPEC_OPT", "default_mode": "TEMP",
        "mode_map": {"TEMP": ["TEMP"], "DUTY": ["DUTY"]}},
    "COMPR": {"mode_param": "SPEC_OPT", "default_mode": "TEMP",
        "mode_map": {"TEMP": ["TEMP"], "DUTY": ["DUTY"], "PRES": ["PRES"], "DELP": ["DELP"]}},
    "RSTOIC": {"mode_param": "SPEC_OPT", "default_mode": "TP",
        "mode_map": {"TP": ["TEMP", "PRES"], "TEMP": ["TEMP"], "PRES": ["PRES"],
                     "DUTY": ["DUTY"], "VFRAC": ["VFRAC"]}},
}


def _read_option_list(param_node):
    '''Read option list from a parameter node.
    For enum-type params (like SPEC_OPT), AttributeValue(5) returns
    the option list node, whose AttributeValue(0) contains
    newline-separated option values.'''
    try:
        opt_node = param_node.AttributeValue(5)
        if opt_node is not None:
            raw = opt_node.AttributeValue(0)
            if raw and isinstance(raw, str):
                return raw.split("\n")
    except Exception:
        pass
    return None


def _get_block_type(tree, block_name):
    '''Get the Aspen block type string (e.g. HEATER, ICON2).'''
    try:
        blk = walk(tree, "Data", "Blocks", block_name)
        if blk is not None:
            return blk.Value
    except Exception:
        pass
    return None


def _read_mode_value(tree, block_name, mode_param):
    '''Read current value of a mode-selector param like SPEC_OPT.'''
    try:
        n = walk(tree, "Data", "Blocks", block_name, "Input", mode_param)
        if n is not None and n.Value:
            return str(n.Value)
    except Exception:
        pass
    return None


def _categorize_block_params(tree, block_name):
    '''Categorize unset-but-active params.

    Returns (critical, irrelevant, optional, mode_info).
    - critical:    need to be filled for current mode
    - irrelevant:  in same or-group but not needed in current mode
    - optional:    not related to any mode
    - mode_info:   human-readable like "SPEC_OPT=TEMP" or None
    '''
    blk_type = _get_block_type(tree, block_name)
    inp = walk(tree, "Data", "Blocks", block_name, "Input")
    if inp is None:
        return [], [], [], None

    mode_config = _BLOCK_MODES.get(blk_type) if blk_type else None
    current_mode = None
    mode_required = set()
    mode_optional = set()

    if mode_config:
        mode_param_name = mode_config["mode_param"]
        current_mode = _read_mode_value(tree, block_name, mode_param_name)
        if not current_mode:
            current_mode = mode_config.get("default_mode")
        mode_map = mode_config.get("mode_map", {})
        if current_mode and current_mode in mode_map:
            mode_required = set(mode_map[current_mode])
        for mode_vals in mode_map.values():
            mode_optional.update(mode_vals)

    mode_info = None
    if mode_config and current_mode:
        mode_info = mode_config["mode_param"] + "=" + current_mode

    _SKIP = frozenset({
        "Unit Set", "User Table", "User Tree",
        "ADDINPUT", "INPUT", "COMPS",
        "DESCRIPTION", "FILE", "COORD",
        "COMMENT", "HEADING", "RESULTS", "REPORT",
        "OPSETNAME", "FRWATEROPSET",
        "SIM_LEVEL", "PROP_LEVEL", "STREAM_LEVEL", "TERM_LEVEL",
    })

    critical = []
    irrelevant = []
    optional = []

    for ii in range(500):
        try:
            n = inp.Elements(ii)
            if n is None:
                break
        except Exception:
            break
        pname = n.Name
        if pname in _SKIP:
            continue
        try:
            i7 = n.AttributeValue(7)
            i11 = n.AttributeValue(11)
            i19 = n.AttributeValue(19)
            i2 = n.AttributeValue(2)
            i3 = n.AttributeValue(3)
        except Exception:
            continue
        if i7 == 0:
            continue
        if i11 == 1:
            continue
        try:
            if n.ValueType != 0 and n.Value is not None:
                continue
        except Exception:
            continue

        line = "    " + pname
        if i19 and str(i19) != pname:
            desc = str(i19)[:60]
            line += "  -- " + desc
        hint = _UNIT_HINTS.get((i2, i3))
        if hint:
            line += "  [" + hint + "]"

        if pname in mode_required:
            critical.append(line)
        elif pname in mode_optional:
            irrelevant.append(line)
        else:
            optional.append(line)

    return critical, irrelevant, optional, mode_info



def _param_diagnostics(tree, block_name: str, max_lines: int = 10) -> list[str]:
    """Scan a block's Input params and return diagnostic lines for unset but active params.
    Uses smart categorization (critical vs irrelevant vs optional) based on SPEC_OPT mode."""
    critical, irrelevant, optional, mode_info = _categorize_block_params(tree, block_name)

    result = []
    if mode_info:
        result.append("    [Mode: " + mode_info + "]")

    if critical:
        result.append("    == Critical (current mode) ==")
        result.extend(critical[:max_lines])
        if len(critical) > max_lines:
            result.append("      ... and " + str(len(critical) - max_lines) + " more")

    if irrelevant:
        result.append("    -- Mode-irrelevant --")
        result.extend(irrelevant[:max(max_lines, 5)])
        if len(irrelevant) > max(max_lines, 5):
            result.append("      ... and " + str(len(irrelevant) - max(max_lines, 5)) + " more")

    if optional and len(result) < max_lines:
        remaining = max_lines - len(result)
        if remaining > 0:
            result.append("    .. Optional ..")
            result.extend(optional[:remaining])
            if len(optional) > remaining:
                result.append("      ... and " + str(len(optional) - remaining) + " more")

    if not result:
        result.append("  (all active params have values)")

    return result


def _get_convergence_report() -> str:
    """Build a convergence report from current simulation state (on COM thread)."""
    tree = aspen._app.RootModel("")
    lines: list[str] = []
    blocks_node = walk(tree, "Data", "Blocks")
    if blocks_node is not None:
        block_lines = []
        blocks_with_issues = []
        for i in range(200):
            try:
                block = blocks_node.Elements(i)
            except Exception:
                break
            if block is None:
                break
            bname = block.Name
            blkstat = walk(tree, "Data", "Blocks", bname, "Output", "BLKSTAT")
            perror = walk(tree, "Data", "Blocks", bname, "Output", "PER_ERROR")
            propstat = walk(tree, "Data", "Blocks", bname, "Output", "PROPSTAT")
            blkmsg = walk(tree, "Data", "Blocks", bname, "Output", "BLKMSG")
            msg = f"  {bname}"
            if blkstat is not None:
                stat_map = {0: "OK", 1: "converged", 2: "not converged", 3: "warning"}
                msg += f"  BLKSTAT={blkstat.Value} ({stat_map.get(blkstat.Value, '?')})"
                if blkstat.Value not in (0, 1, None):
                    blocks_with_issues.append(bname)
            if perror is not None:
                msg += f"  PER_ERROR={perror.Value}"
            if propstat is not None:
                msg += f"  PROPSTAT={propstat.Value}"
            if blkmsg is not None and blkmsg.Value:
                msg += f"  BLKMSG={blkmsg.Value}"
            block_lines.append(msg)
        if block_lines:
            lines.append("Block convergence status:")
            lines.extend(block_lines)
        if blocks_with_issues:
            lines.append("")
            lines.append("Parameter diagnostics (unset params in troubled blocks):")
            for bname in blocks_with_issues:
                diag = _param_diagnostics(tree, bname)
                if diag:
                    lines.append(f"  [{bname}]:")
                    lines.extend(diag)

    return "\n".join(lines)


# --- find_incomplete_inputs --------------------------------------------------


@mcp_tool
def tool_find_incomplete_inputs() -> str:
    """Scan the simulation for incomplete input nodes.

    Uses smart categorization per block type:
    - For known block types (HEATER, ICON2, V-DRUM1, etc.), reads SPEC_OPT
      to determine which params are truly required vs optional in current mode.
    - Unknown block types: list all active-but-unset params (traditional).
    """
    def impl():
        tree = aspen._app.RootModel("")
        blks = walk(tree, "Data", "Blocks")
        if blks is None:
            return "No Blocks node found"

        results = []
        for bi in range(500):
            try:
                blk = blks.Elements(bi)
            except Exception:
                break
            if blk is None:
                break
            blk_name = blk.Name
            blk_type = _get_block_type(tree, blk_name)

            critical, irrelevant, optional, mode_info = _categorize_block_params(tree, blk_name)

            if not (critical or irrelevant or optional):
                continue

            header = "  [" + blk_name
            if blk_type:
                header += " (" + blk_type + ")"
            if mode_info:
                header += "]  Current mode: " + mode_info
            else:
                header += "]"
            results.append(header)

            if critical:
                results.append("    == Critical (needed for current mode) ==")
                results.extend(critical)

            if irrelevant:
                results.append("    -- Mode-irrelevant (needed if mode changes) --")
                shown = irrelevant[:5]
                for item in shown:
                    results.append(item)
                if len(irrelevant) > 5:
                    results.append("      ... and " + str(len(irrelevant) - 5) + " more")

            if optional:
                results.append("    .. Other optional params ..")
                shown = optional[:5]
                for item in shown:
                    results.append(item)
                if len(optional) > 5:
                    results.append("      ... and " + str(len(optional) - 5) + " more")

            results.append("")

        # Also check utilities
        util_lines = _check_utilities_completeness(tree)

        if not results and not util_lines:
            return "All inputs appear complete."

        if util_lines:
            results = util_lines + results

        return "Params likely needing input:\n" + "\n".join(results).rstrip("\n\n")
    return aspen.call(impl)


def _check_utilities_completeness(tree) -> list[str]:
    """Check all defined utilities for missing critical parameters.

    Returns a list of formatted lines (empty if all utilities are complete).
    """
    CRITICAL_UTIL_PARAMS = {
        "WATER": [
            "UTILITY_TYPE", "TIN", "TOUT", "PRES", "VFRAC",
            "CO2FACTOR", "HTC", "ENERGY_PRICE", "PRICE",
            "COOLING_VALU", "DENSITY", "VISCOSITY", "CONDUCTIVITY",
            "FACTORSOURCE",
        ],
        "STEAM": [
            "UTILITY_TYPE", "PRES", "VFRAC", "TIN", "TOUT",
            "CO2FACTOR", "HTC", "ENERGY_PRICE", "PRICE",
            "COOLING_VALU", "DENSITY", "VISCOSITY", "CONDUCTIVITY",
            "FACTORSOURCE", "FUELSOURCE",
        ],
        "ELECTRICITY": [
            "UTILITY_TYPE", "ELEC_PRICE",
            "CO2FACTOR", "HTC", "ENERGY_PRICE", "PRICE",
            "FACTORSOURCE", "FUELSOURCE",
        ],
        "REFRIGERANT": [
            "UTILITY_TYPE", "PRES", "VFRAC",
            "CO2FACTOR", "HTC", "ENERGY_PRICE",
        ],
        "FUEL": [
            "UTILITY_TYPE", "PRES", "VFRAC",
            "CO2FACTOR", "HTC", "ENERGY_PRICE",
        ],
    }

    utils = walk(tree, "Data", "Utilities")
    if utils is None:
        return []

    lines = []
    for i in range(200):
        try:
            util = utils.Elements(i)
        except Exception:
            break
        if util is None:
            break
        name = util.Name
        if name in ("Input", "Output", "CC Nodes"):
            continue

        # Determine type
        utype = None
        for pi in range(200):
            try:
                c = util.Elements(pi)
            except Exception:
                break
            if c is None:
                break
            if c.Name == "Input":
                try:
                    utype = c.Elements("UTILITY_TYPE").Value
                except Exception:
                    pass
                break

        if not utype:
            utype = "UNKNOWN"
        utype_upper = utype.upper()

        # Look up which params to check
        check_list = CRITICAL_UTIL_PARAMS.get(utype_upper, CRITICAL_UTIL_PARAMS.get("WATER"))

        missing = []
        inp = walk(tree, "Data", "Utilities", name, "Input")
        if inp is None:
            continue

        for pname in check_list:
            try:
                p = inp.Elements(pname)
                if p is None or p.Value is None:
                    missing.append(pname)
            except Exception:
                missing.append(pname)

        if missing:
            lines.append(f"  [{name}] ({utype}) -- missing: {', '.join(missing)}")

    if lines:
        lines.insert(0, "--- Utilities needing input ---")
        lines.append("")
    return lines


@mcp_tool
def tool_validate_block(block_name: str) -> str:
    """Check block validation status with parameter-level diagnostics.

    Reports Engine.Ready, block status, and scans active unset params
    with Chinese descriptions and unit hints.
    """
    def impl():
        lines = []
        try:
            eng = aspen._app.Engine
            lines.append(f"Engine.Ready = {eng.Ready}")
            lines.append(f"Engine.IsRunning = {eng.IsRunning}")
        except Exception as e:
            lines.append(f"Engine error: {e}")

        tree = aspen._app.RootModel("")
        blk = walk(tree, "Data", "Blocks", block_name)
        if blk is not None:
            lines.append(f"Block type = {blk.Value}")

            # Run convergence info
            out = walk(tree, "Data", "Blocks", block_name, "Output")
            if out is not None:
                blkstat = walk(tree, "Data", "Blocks", block_name, "Output", "BLKSTAT")
                blkmsg = walk(tree, "Data", "Blocks", block_name, "Output", "BLKMSG")
                perror = walk(tree, "Data", "Blocks", block_name, "Output", "PER_ERROR")
                if blkstat is not None:
                    smap = {0: "OK", 1: "converged", 2: "not converged", 3: "warning"}
                    lines.append(f"BLKSTAT = {blkstat.Value} ({smap.get(blkstat.Value, '?')})")
                if perror is not None:
                    lines.append(f"PER_ERROR = {perror.Value}")
                if blkmsg is not None and blkmsg.Value:
                    lines.append(f"BLKMSG = {blkmsg.Value}")

            # Parameter diagnostics
            lines.append("")
            lines.append("Parameter diagnostics (active but unset):")
            diag = _param_diagnostics(tree, block_name, max_lines=15)
            if diag:
                lines.extend(diag)
            else:
                lines.append("  (all active params have values)")

        return "\n".join(lines)
    return aspen.call(impl)
