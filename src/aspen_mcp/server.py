"""
aspen_mcp.server — FastMCP entry point.

Registers all tools and runs the MCP server on stdio.
"""

from __future__ import annotations

import logging
import sys

from fastmcp import FastMCP

from .com_bridge import aspen
from .tools.simulation import (
    tool_status,
    tool_open_file,
    tool_close_file,
    tool_run,
    tool_run_async,
    tool_save,
    tool_reinit,
    tool_reinit_and_run,
    tool_new_simulation,
    tool_stop_simulation,
    tool_visible,
    tool_run_script,
    tool_batch_refresh,
)
from .tools.streams import (
    tool_list_all_streams,
    tool_get_stream,
    tool_get_stream_composition_info,
    tool_set_stream_param,
    tool_set_stream_composition,
    tool_set_stream_composition_batch,
    tool_add_stream,
    tool_remove_stream,
    tool_connect,
    tool_connect_port,
    tool_disconnect,
    tool_list_block_ports,
)
from .tools.blocks import (
    tool_list_all_blocks,
    tool_get_block,
    tool_block_status,
    tool_set_param,
    tool_add_block,
    tool_remove_block,
    tool_explore,
)
from .tools.components import (
    tool_list_components,
    tool_add_component,
    tool_remove_component,
    tool_get_property_method,
    tool_set_property_method,
)
from .tools.reactions import (
    tool_add_reaction_set,
    tool_remove_reaction_set,
    tool_add_reaction,
    tool_remove_reaction,
    tool_list_reaction_sets,
    tool_setup_block_reaction,
)
from .tools.analysis import (
    tool_sensitivity,
    tool_export_report_file,
    tool_diagnose,
    tool_search_convergence_knowledge,
    tool_generate_input_summary,
    tool_find_incomplete_inputs,
    tool_list_tear_streams,
    tool_set_tear_estimate,
    tool_validate_block,
    tool_probe_f4,
    tool_simulation_warnings,
)
from .tools.deep_probe import tool_deep_probe
from .tools.fix_trivial import tool_fill_trivial_params
from .tools.flowsheet import (
    tool_flowsheet_topology,
    tool_add_side_duty,
    tool_remove_side_duty,
    tool_configure_fsplit,
    tool_list_all_ports,
    cache_block_type,
    uncache_block_type,
)
from .tools.columns import (
    tool_set_column_stages,
    tool_set_condenser_type,
    tool_set_reboiler_type,
    tool_set_feed_stage,
    tool_set_product_stage,
    tool_set_column_pressure,
)
from .tools.cache_tools import (
    tool_get_call_log,
    tool_clear_call_log,
    tool_get_sensitivity_history,
    tool_clear_sensitivity_cache,
)
from .tools.sensitivity_advanced import (
    tool_sensitivity_advanced,
)
from .tools.help_content import get_help
from .tools.paths import (
    tool_get_value,
    tool_set_value,
    tool_insert_row,
)

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s  %(name)s  %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("aspen_mcp")

# Initialize COM on the main thread so that COM proxy objects returned
# from the COM apartment thread can be marshalled correctly.
try:
    import pythoncom
    pythoncom.CoInitialize()
    logger.info("CoInitialize on main thread")
except Exception:
    pass


def create_server() -> FastMCP:
    mcp = FastMCP("Aspen Plus MCP")

    # ── simulation ───────────────────────────────────────────────────────

    @mcp.tool()
    def status() -> dict:
        """Get the Aspen Plus connection and engine status."""
        return tool_status()

    @mcp.tool()
    def probe() -> dict:
        """Diagnose COM state (app, root, tree access)."""
        try:
            return aspen.probe()
        except Exception as exc:
            return {"error": str(exc)}

    @mcp.tool()
    def open_file(file_path: str) -> str:
        """Open an Aspen Plus .apw simulation file."""
        return tool_open_file(file_path)

    @mcp.tool()
    def close_file() -> str:
        """Close the currently-open simulation file.
        
        After closing, clears the COM reference on the main thread
        so the next call() auto-reconnects cleanly.
        """
        return tool_close_file()

    @mcp.tool()
    def run() -> str:
        """Run the simulation.

        Has 30-second timeout — if the engine hangs, it is stopped
        and a "Timeout:" error is returned.
        Before running, automatically checks feed streams for
        TEMP/PRES/composition. After run, checks BLKSTAT/BLKMSG.
        """
        return tool_run()

    @mcp.tool()
    def run_async() -> str:
        """Run the simulation (asynchronous)."""
        return tool_run_async()

    @mcp.tool()
    def save(file_path: str | None = None) -> str:
        """Save the simulation. Optionally provide a SaveAs path."""
        return tool_save(file_path)

    @mcp.tool()
    def reinit() -> str:
        """Reinitialize the simulation (reset results)."""
        return tool_reinit()

    @mcp.tool()
    def reinit_and_run() -> str:
        """Reinitialize then run (with 30s timeout).

        If the simulation hangs, it is stopped automatically
        and a "Timeout:" error is returned.
        Before running, automatically checks feed streams for
        TEMP/PRES/composition. After run, checks BLKSTAT/BLKMSG.
        """
        return tool_reinit_and_run()

    @mcp.tool()
    def new_simulation() -> str:
        """Create a new blank simulation from the built-in template.

        Closes any open file first, copies blank template to %%TEMP%%,
        then opens the copy. Template has 0 components and empty topology.
        Uses a bundled template so no external files are needed.
        """
        return tool_new_simulation()

    @mcp.tool()
    def stop_simulation() -> str:
        """Stop the currently running simulation."""
        return tool_stop_simulation()

    @mcp.tool()
    def visible(show: bool) -> str:
        """Show or hide the Aspen Plus GUI window."""
        return tool_visible(show)

    @mcp.tool()
    def run_script(file_path: str) -> str:
        """Execute a Python script inside Aspen Plus."""
        return tool_run_script(file_path)

    @mcp.tool()
    def batch_refresh(off: bool) -> str:
        """Disable or re-enable GUI refresh (speed up bulk operations)."""
        return tool_batch_refresh(off)

    # ── streams ──────────────────────────────────────────────────────────

    @mcp.tool()
    def list_all_streams() -> list[str]:
        """List all stream names in the flowsheet."""
        return tool_list_all_streams()

    @mcp.tool()
    def get_stream(name: str) -> dict:
        """Read stream output properties (temp, pressure, flows, etc.)."""
        return tool_get_stream(name)

    @mcp.tool()
    def get_stream_composition_info(name: str) -> dict:
        """Get stream composition metadata (COMPTYPE, MW, flows)."""
        return tool_get_stream_composition_info(name)

    @mcp.tool()
    def set_stream_param(stream_name: str, param: str, value: float, basis: str | None = None) -> str:
        """Set a stream input parameter (TEMP, PRES, TOTAL, or component with BASIS).

        ⚠️  Aspen 物流参数必须通过此工具设置，不能直接用 set_param。
            自动处理 MIXED 子节点写入逻辑。

        Common params: TEMP (温度), PRES (压力), TOTAL (总流量).
        basis: 可选——MOLE-FLOW, MASS-FLOW, MOLE-FRAC, MASS-FRAC.
        Unit is determined by the current Unit-Set.
        """
        return tool_set_stream_param(stream_name, param, value, basis)

    @mcp.tool()
    def set_stream_composition(stream_name: str, component: str, flow: float) -> str:
        """Set a component's molar flow in a stream.

        NOTE: IDs over 8 chars get truncated (PROPYLENE -> PROPYLEN).
        Use list_components() to see actual labels.

        Args:
            stream_name: Stream name.
            component: Component label (confirmed via list_components).
            flow: Molar flow (unit depends on Unit-Set).
        """
        return tool_set_stream_composition(stream_name, component, flow)

    @mcp.tool()
    def set_stream_composition_batch(stream_name: str, components: dict[str, float],
                                     basis: str = "MOLE-FLOW",
                                     total_flow: float | None = None) -> str:
        """Batch-set stream composition with BASIS control and optional total flow.

        Handles BASIS switching, all components, and total flow in one call.
        Use this instead of calling set_stream_composition repeatedly.

        Args:
            stream_name: Stream name (e.g. 'FEED').
            components: {component_id: value} dict.
            basis: MOLE-FLOW (default), MASS-FLOW, MOLE-FRAC, MASS-FRAC.
            total_flow: Required when basis is a fraction (e.g. MOLE-FRAC).

        Examples:
            set_stream_composition_batch("FEED", {"ETHANOL": 50, "WATER": 50})
            set_stream_composition_batch("FEED", {"ETHANOL": 0.5, "WATER": 0.5},
                                         basis="MOLE-FRAC", total_flow=100)
        """
        return tool_set_stream_composition_batch(stream_name, components, basis, total_flow)

    @mcp.tool()
    def add_stream(name: str) -> str:
        """Add a new stream to the flowsheet."""
        return tool_add_stream(name)

    @mcp.tool()
    def remove_stream(name: str) -> str:
        """Remove a stream from the flowsheet."""
        return tool_remove_stream(name)

    @mcp.tool()
    def connect(source_block: str, dest_block: str, stream_name: str | None = None,
                  source_port: str | None = None, dest_port: str | None = None) -> str:
        """Connect source_block to dest_block via an auto-created or specified stream.

        Auto-creates the stream if it doesn't exist.
        Default ports: P(OUT) on source, F(IN) on destination.
        Override with source_port/dest_port for non-standard ports
        (e.g. V(OUT) for FLASH2 vapor, L(OUT) for FLASH2 liquid).
        """
        return tool_connect(source_block, dest_block, stream_name, source_port, dest_port)

    @mcp.tool()
    def connect_port(block_name: str, port_name: str, stream_name: str) -> str:
        """Connect a stream to a single block port.

        APPEND mode: does NOT clear port. Multiple streams on same port OK.
        If stream is already connected, does nothing.
        NOTE: Re-open .apw to refresh visual connections.
        Use list_block_ports to see available ports.
        """
        return tool_connect_port(block_name, port_name, stream_name)

    @mcp.tool()
    def disconnect(stream_name: str) -> str:
        """Disconnect a stream from all ports and remove it.
        
        Now uses a snapshot-first algorithm to safely handle partial failures.
        Scans all connections first, removes from ports one-by-one,
        and only removes from the Streams collection if all port removals succeeded.
        This prevents crashes on remove_block() after a failed disconnect.
        """
        return tool_disconnect(stream_name)

    @mcp.tool()
    def list_block_ports(block_name: str) -> str:
        """List available ports on a block and which streams are connected."""
        return tool_list_block_ports(block_name)

    # ── blocks ───────────────────────────────────────────────────────────

    @mcp.tool()
    def list_all_blocks() -> list[str]:
        """List all block names in the flowsheet."""
        return tool_list_all_blocks()

    @mcp.tool()
    def get_block(name: str) -> dict:
        """Read block specification and results."""
        return tool_get_block(name)

    @mcp.tool()
    def set_param(block_name: str, param: str, value: str | float) -> str:
        """Set a block parameter value.

        Only for block parameters (TEMP, PRES, HEATOPT, etc.).
        Do NOT use for stream parameters -- use set_stream_param instead.
        """
        return tool_set_param(block_name, param, value)

    @mcp.tool()
    def add_block(name: str, block_type: str) -> str:
        """Add a block (HEATER, MIXER, RGIBBS, RPLUG, RCSTR, RSTOIC, etc).

        RGIBBS: just TEMP+PRES, no RXN_ID needed.
        RPLUG/RCSTR: use insert_row + set_value for RXN_ID.
        RStoic: use setup_block_reaction() for block-level stoichiometry.
        """
        result = tool_add_block(name, block_type)
        if result.startswith("Block '"):
            cache_block_type(name, block_type)
        return result

    @mcp.tool()
    def remove_block(name: str) -> str:
        """Remove a block from the flowsheet.

        IMPORTANT: Disconnect all connected streams first with disconnect(),
        then remove the block. Wrong order can crash the COM server.
        Use list_block_ports(name) to see active connections.
        """
        uncache_block_type(name)
        return tool_remove_block(name)

    @mcp.tool()
    def block_status(name: str) -> dict:
        """Read block convergence status (BLKSTAT, PER_ERROR, PROPSTAT, BLKMSG).

        BLKSTAT: 0=OK (success), 1=converged, 2=not converged (ran but diverged), 3=warning.
        BLKSTAT=0 is the normal success state in Aspen v15.
        BLKMSG has the actual Aspen error text (more useful than BLKSTAT).
        """
        return tool_block_status(name)

    @mcp.tool()
    def explore(path: str) -> dict:
        """Explore the Aspen Plus object tree at a backslash path (e.g. Data\\Properties)."""
        return tool_explore(path)

    # ── components / property ───────────────────────────────────────────────

    @mcp.tool()
    def list_components() -> list[str]:
        """List all components in the simulation."""
        return tool_list_components()

    @mcp.tool()
    def add_component(component_id: str) -> str:
        """Add a component to the simulation (e.g. WATER, ETHANOL).

        NOTE: IDs over 8 chars get truncated (PROPYLENE -> PROPYLEN).
        Use list_components() after adding to see the actual label.
        Column 2 (type) is auto-filled by Aspen.
        """
        return tool_add_component(component_id)

    @mcp.tool()
    def remove_component(component_id: str) -> str:
        """Remove a component from the simulation."""
        return tool_remove_component(component_id)

    @mcp.tool()
    def get_property_method() -> str:
        """Get the current global property method (e.g. PENG-ROB, NRTL)."""
        return tool_get_property_method()

    @mcp.tool()
    def set_property_method(method: str) -> str:
        """Set the global property method (e.g. NRTL, PENG-ROB, UNIQUAC, IDEAL)."""
        return tool_set_property_method(method)

    # ── reactions ───────────────────────────────────────────────────────────

    @mcp.tool()
    def add_reaction_set(name: str, reaction_type: str = "POWERLAW") -> str:
        """Create a new reaction set (POWERLAW, LHHW, GENERAL, EQUILIBRIUM)."""
        return tool_add_reaction_set(name, reaction_type)

    @mcp.tool()
    def remove_reaction_set(name: str) -> str:
        """Remove a reaction set and all its reactions."""
        return tool_remove_reaction_set(name)

    @mcp.tool()
    def add_reaction(
        reaction_set: str,
        reaction_no: int,
        reactants: dict[str, float],
        products: dict[str, float],
        phase: str = "L",
        exponents: dict[str, float] | None = None,
    ) -> str:
        r"""Add a reaction with stoichiometry to a reaction set.

        Args:
            reaction_set: Reaction set name (e.g. R-1).
            reaction_no: Reaction number (usually 1).
            reactants: {component_id: coefficient}, e.g. {"ETHYLENE": 1, "WATER": 1}
            products: {component_id: coefficient}, e.g. {"ETHANOL": 1}
            phase: 'L' (liquid) or 'V' (vapor).
            exponents: {component_id: exponent}. Defaults to abs(reactant coeff).

            NOTE: Assign to RPLUG/RCSTR:
              insert_row(r"\Data\Blocks\R-1\Input\RXN_ID")
              set_value(r"\Data\Blocks\R-1\Input\RXN_ID\#0", "R-1")
        """
        return tool_add_reaction(reaction_set, reaction_no, reactants, products, phase, exponents)

    @mcp.tool()
    def remove_reaction(reaction_set: str, reaction_no: int) -> str:
        """Remove a single reaction from a reaction set."""
        return tool_remove_reaction(reaction_set, reaction_no)

    @mcp.tool()
    def list_reaction_sets() -> list[str]:
        """List all reaction sets."""
        return tool_list_reaction_sets()

    @mcp.tool()
    def setup_block_reaction(
        block_name: str,
        reaction_no: int = 1,
        temperature: float | None = None,
        pressure: float | None = None,
        reactants: dict[str, float] | None = None,
        products: dict[str, float] | None = None,
        key_component: str | None = None,
        conversion: float | None = None,
    ) -> str:
        """Set up a stoichiometric reaction inside a block (RStoic, RYield, etc.).

        Some reactor blocks store stoichiometry internally via
        block-level 2D tables (COEF/COEF1) rather than external reaction
        sets. This tool handles that pattern.

        Currently supports RStoic. Extensible to other block types.

        Args:
            block_name: Block name (e.g. R-1).
            reaction_no: Reaction number (1-based).
            temperature: Operating temperature (C). Sets SPEC_OPT=TP.
            pressure: Operating pressure (bar).
            reactants: {component_id: coefficient}, e.g. {"ETHYLENE": 1, "WATER": 1}
            products: {component_id: coefficient}, e.g. {"ETHANOL": 1}
            key_component: Key reactant for conversion (defaults to first reactant).
            conversion: Fractional conversion of key component (0.0-1.0).

            NOTE: Coefficients should be positive - the tool auto-negates
            for reactants and sets them positive for products.
        """
        return tool_setup_block_reaction(
            block_name, reaction_no, temperature, pressure,
            reactants, products, key_component, conversion,
        )

    # ── flowsheet topology ───────────────────────────────────────────────

    @mcp.tool()
    def flowsheet_topology() -> str:
        """Show the flowsheet topology: source --[stream]--> destination."""
        return tool_flowsheet_topology()

    @mcp.tool()
    def add_side_duty(block_name: str, stage: int, duty: float) -> str:
        """Add/update a side heater/cooler duty on a RadFrac stage."""
        return tool_add_side_duty(block_name, stage, duty)

    @mcp.tool()
    def remove_side_duty(block_name: str, stage: int) -> str:
        """Remove a side duty from a RadFrac stage."""
        return tool_remove_side_duty(block_name, stage)

    # ── generic path access ──────────────────────────────────────────────

    @mcp.tool()
    def get_value(path: str) -> str:
        """Read a value by backslash path (e.g. \\Data\\Streams\\S1\\Output\\RES_TEMP)."""
        return tool_get_value(path)

    @mcp.tool()
    def set_value(path: str, value: str | float, unit: str | None = None) -> str:
        """Write a value by backslash path (e.g. \\Data\\Blocks\\B1\\Input\\TEMP)."""
        return tool_set_value(path, value, unit)

    @mcp.tool()
    def insert_row(path: str, dimension: int = 0) -> str:
        r"""Insert a new row in a table-type node.

        CRITICAL for RPLUG/RCSTR: RXN_ID starts empty (0 rows).
        You MUST insert_row BEFORE set_value:
          insert_row("\Data\Blocks\R-1\Input\RXN_ID")
          set_value("\Data\Blocks\R-1\Input\RXN_ID\#0", "R-1")

        Args:
            path: Backslash path to the table node.
            dimension: Table dimension (default 0).
        """
        return tool_insert_row(path, dimension)

    # ── analysis ─────────────────────────────────────────────────────────

    @mcp.tool()
    def sensitivity(
        block_name: str,
        variable: str,
        values: list[float],
        unit: str = "",
    ) -> dict:
        """Manual sensitivity: sweep a block variable and re-run."""
        return tool_sensitivity(block_name, variable, values, unit)

    @mcp.tool()
    def export_report_file(file_path: str) -> str:
        """Export the simulation report to a .rep file."""
        return tool_export_report_file(file_path)

    @mcp.tool()
    def diagnose(keywords: list[str]) -> str:
        """Diagnose convergence issues: live status + knowledge base search.

        BLKSTAT=0 = OK (normal). BLKSTAT=2 = not converged (ran but diverged).
        BLKSTAT=2 = not converged (ran but diverged).
        BLKMSG has the actual Aspen error text.

        Args:
            keywords: Keywords to search the knowledge base
                      (e.g. ["Wegstein"], ["COLUMN DRIES UP"], ["NRTL"]).
        """
        return tool_diagnose(keywords)

    @mcp.tool()
    def search_convergence_knowledge(keywords: list[str]) -> list[dict]:
        """Search convergence troubleshooting knowledge base (verbose).

        Also searches convergence method guide and common error table.
        Use diagnose() for a human-readable report with live status.
        """
        return tool_search_convergence_knowledge(keywords)

    @mcp.tool()
    def generate_input_summary(file_path: str) -> str:
        """Generate an input summary file (.bkp) for debugging."""
        return tool_generate_input_summary(file_path)

    @mcp.tool()
    def find_incomplete_inputs() -> str:
        """Scan the simulation for incomplete input nodes.

        Uses smart categorization per block type:
        - Reads SPEC_OPT to determine the current operating mode
        - Groups params into Critical / Mode-irrelevant / Optional
        - Critical params are the ones that truly need filling for the current mode
        - Mode-irrelevant params can be ignored (only matter if mode changes)

        For unknown block types, lists all active-but-unset params as before.
        CC Nodes/Output/User Table are filtered out.
        """
        return tool_find_incomplete_inputs()

    # -- tear streams -------------------------------------------------------

    @mcp.tool()
    def list_tear_streams() -> list[str]:
        """List all tear streams in the simulation (recycle loops)."""
        return tool_list_tear_streams()

    @mcp.tool()
    def set_tear_estimate(stream_name: str, temp: float | None = None,
                           pres: float | None = None,
                           total_flow: float | None = None) -> str:
        """Set initial estimate for a tear (recycle) stream.

        Args:
            stream_name: Tear stream name.
            temp: Estimated temperature (C).
            pres: Estimated pressure (bar).
            total_flow: Estimated total molar flow (kmol/hr).
        """
        return tool_set_tear_estimate(stream_name, temp, pres, total_flow)

    # -- simulation warnings -------------------------------------------------

    @mcp.tool()
    def simulation_warnings() -> list[str]:
        """Scan for common config issues (pressure mismatch, unconnected feeds)."""
        return tool_simulation_warnings()

    @mcp.tool()
    def probe_f4() -> str:
        """Deep probe Aspen COM for F4/NextRequiredInput methods."""
        return tool_probe_f4()

    @mcp.tool()
    def validate_block(block_name: str) -> str:
        """Check block validation status (Engine.Ready, input completeness, errors)."""
        return tool_validate_block(block_name)

    @mcp.tool()
    def fill_trivial_params() -> str:
        """Fill trivial/meaningless active-but-unset parameters across all blocks.

        Many parameters show up in find_incomplete_inputs() because they are
        "active" (i7=1) but never filled — they are COM infrastructure, UI
        artifacts, estimation placeholders, or dynamic/holdup params irrelevant
        to steady-state simulation. This function fills them with safe defaults
        (0 for numbers, "" for strings) so that subsequent diagnostics only
        show the truly important missing parameters.
        """
        return tool_fill_trivial_params()

    @mcp.tool()
    def deep_probe(block_name: str = "") -> str:
        """Deep probe a block's input node properties for validation info."""
        return tool_deep_probe(block_name)

    # -- fsplit ---------------------------------------------------------------

    @mcp.tool()
    def configure_fsplit(block_name: str, outlet_name: str, frac: float) -> str:
        """Add/configure a second product outlet on an FSPLIT block.

        Args:
            block_name: FSPLIT block name (e.g. S-1).
            outlet_name: Product stream name (e.g. RECYCLE).
            frac: Split fraction (0.0-1.0) for this outlet.
        """
        return tool_configure_fsplit(block_name, outlet_name, frac)

    @mcp.tool()
    def list_all_ports() -> str:
        """List all block ports and connected streams across the entire flowsheet.

        One-command overview of every block, port names, and connected streams.
        Use before connect() to see available ports, or before disconnect().
        """
        return tool_list_all_ports()


    # -- column configuration ---------------------------------------------------

    @mcp.tool()
    def set_column_stages(block_name: str, nstage: int) -> str:
        """Set the number of stages on a RadFrac / ABSBR1 column.

        NSTAGE is the total number of theoretical stages (including
        condenser and reboiler if present).

        Args:
            block_name: Column block name (e.g. 'HPD', 'C1').
            nstage: Number of stages (integer >= 2).
        """
        return tool_set_column_stages(block_name, nstage)

    @mcp.tool()
    def set_condenser_type(block_name: str, condenser_type: str) -> str:
        """Set the condenser type on a RadFrac column.

        Args:
            block_name: Column block name.
            condenser_type: One of 'NONE', 'TOTAL', 'PARTIAL-V',
                            'PARTIAL-L', 'PARTIAL-VL'.
        """
        return tool_set_condenser_type(block_name, condenser_type)

    @mcp.tool()
    def set_reboiler_type(block_name: str, reboiler_type: str) -> str:
        """Set the reboiler type on a RadFrac column.

        Args:
            block_name: Column block name.
            reboiler_type: One of 'NONE', 'KETTLE', 'THERMOSIPHON',
                           'INTERNALS', 'FIRED'.
        """
        return tool_set_reboiler_type(block_name, reboiler_type)

    @mcp.tool()
    def set_feed_stage(block_name: str, stream_name: str, stage: int) -> str:
        """Set the feed stage for a stream entering a column.

        The stream must already be connected to the column via connect()
        or connect_port().

        Args:
            block_name: Column block name.
            stream_name: Feed stream name.
            stage: Stage number (1 = top, NSTAGE = bottom).
        """
        return tool_set_feed_stage(block_name, stream_name, stage)

    @mcp.tool()
    def set_product_stage(block_name: str, stream_name: str,
                           stage: int, phase: str = "L") -> str:
        """Set the product draw stage and phase for a column product stream.

        Args:
            block_name: Column block name.
            stream_name: Product stream name.
            stage: Stage number from which to draw.
            phase: 'L' (liquid, default) or 'V' (vapor).
        """
        return tool_set_product_stage(block_name, stream_name, stage, phase)

    @mcp.tool()
    def set_column_pressure(block_name: str, top_pres: float,
                             dp_stage: float | None = None) -> str:
        """Set the column pressure profile.

        Args:
            block_name: Column block name.
            top_pres: Pressure at the top stage (in current unit-set, e.g. bar).
            dp_stage: Optional pressure drop per stage. If omitted, constant
                      pressure is assumed.
        """
        return tool_set_column_pressure(block_name, top_pres, dp_stage)

        # -- sensitivity advanced ------------------------------------------------

    @mcp.tool()
    def sensitivity_advanced(
        block_name: str,
        variable: str,
        values: list[float],
        linked_params: dict[str, float] | None = None,
        targets: list[str] | None = None,
        feed_stream: str | None = None,
        feed_temp: float | None = None,
        feed_pres: float | None = None,
        feed_composition: dict[str, float] | None = None,
        title: str = "",
    ) -> dict:
        """Sweep a block variable with linked params and collect results."""
        return tool_sensitivity_advanced(
            block_name, variable, values, linked_params, targets,
            feed_stream, feed_temp, feed_pres, feed_composition, title,
        )

    # -- cache / call log ---------------------------------------------------

    @mcp.tool()
    def get_call_log(limit: int = 20) -> list[dict]:
        """Show recent tool call history (up to 200 saved)."""
        return tool_get_call_log(limit)

    @mcp.tool()
    def clear_call_log() -> str:
        """Clear the tool call history."""
        return tool_clear_call_log()

    @mcp.tool()
    def get_sensitivity_history() -> list[dict]:
        """Show all saved sensitivity analysis results."""
        return tool_get_sensitivity_history()

    @mcp.tool()
    def clear_sensitivity_cache() -> str:
        """Clear all cached sensitivity results."""
        return tool_clear_sensitivity_cache()

    # -- help ----------------------------------------------------------------

    @mcp.tool()
    def help(topic: str | None = None) -> str:
        """Get detailed usage guide for Aspen MCP workflows.

        Topics: workflow-basic, workflow-from-scratch, workflow-reaction,
                block-reaction, deletion-order, com-recovery, stream-params,
                reaction-manual, component-facts, tips, pitfalls, dev-pattern,
                attribute-values, set-params, diagnostics,
                fill-trivial-params, com-sta-conflict, quick-start.

        Workflow rule: ALWAYS run find_incomplete_inputs() before reinit_and_run().

          diagnostics       -- find_incomplete_inputs (smart categorization), validate_block, diagnose
          fill-trivial-params -- fill infrastructure/UI-artifact params with safe defaults
          attribute-values -- COM metadata index meanings (i2, i3, i7, i11, i19)
          set-params       -- unit hints + range display on set_param/set_stream_param
          list-all-ports   -- one-command view of every block ports and connected streams
          block-reaction   -- setup stoichiometric reactions in RStoic blocks
          quick-start      -- one-page overview of every tool and workflow

        Call without arguments to list all topics.
        """
        return get_help(topic)

    logger.info("All tools registered")
    return mcp


mcp_server = create_server()


def main() -> None:
    """Entry point: connect to Aspen and run the MCP server."""
    mcp_server.run(transport="stdio")


if __name__ == "__main__":
    main()
