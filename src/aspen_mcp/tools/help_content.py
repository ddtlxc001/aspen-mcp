"""Workflow guides for the Aspen MCP help() tool.

This file contains static help text for common workflows and usage patterns.
The help() tool in server.py delegates to get_help() here.

== How to use this file ==
Agent: when you need workflow guidance, call help("topic-name").
Topics cover: build-from-scratch, reactions, deletion, COM recovery,
attribute-values, diagnostics, set-params, and discovered COM metadata.
"""

HELP_TOPICS: dict[str, str] = {}


def _init():
    global HELP_TOPICS
    HELP_TOPICS = {
        "workflow-basic": """
# Basic Workflow: Parameter Tuning

Use when: topology is already drawn in GUI, just need to set parameters and run.

  1. open_file("path.apw")          # Open existing simulation
  2. set_param("B1", "TEMP", 150)   # Set block params (use set_stream_param for streams)
  3. reinit_and_run()               # Clear cache + run (30s timeout)
  4. get_stream("S1")               # Read results

Tip: set_param now auto-reports [unit] and range=(min, max).
     see help("set-params") for details.
""",
        "workflow-from-scratch": """
# Complete Workflow: Build from Scratch

  1. new_simulation()               # Create blank sim (auto-closes any open file)
  2. add_component("WATER")         # Add components first
     add_component("ETHANOL")
  3. set_property_method("NRTL")    # Set property method
  4. add_block("MIXER", "MIXER")    # Add blocks
     add_block("HEATER", "HEATER")
  5. add_stream("FEED")             # Add streams
  6. connect("MIXER", "HEATER", "FEED")  # Connect blocks (default ports)
     connect("V-1", "VAPOR", source_port="V(OUT)", dest_port="F(IN)")  # Custom ports
  7. set_stream_param("FEED", "TEMP", 100)  # Stream params: use set_stream_param
     set_stream_param("FEED", "PRES", 2)
     set_param("HEATER", "TEMP", 200)      # Block params: use set_param
  8. find_incomplete_inputs()       # Check what's still missing (enhanced: shows chinese desc + units)
  9. reinit_and_run()               # Run
 10. get_stream("HEATER-OUT")       # Read results
 11. validate_block("HEATER")       # Check convergence + param diagnostics after run

Order: components -> property method -> topology -> params -> diagnostics -> run.
""",
        "workflow-reaction": """
# Reaction Workflow: Add Kinetics

After topology is built:

  1. add_reaction_set("R-1")                    # Create reaction set (POWERLAW)
  2. add_reaction("R-1", 1,                     # Add reaction
       reactants={"CO2": 1, "H2": 4},
       products={"CH4": 1, "H2O": 2},
       phase="V")
  3. # Set kinetic parameters
     set_value("DATA\\Reactions\\Reactions\\R-1\\Input\\PRE_EXP\\1", 1.0e8)
     set_value("DATA\\Reactions\\Reactions\\R-1\\Input\\ACT_ENERGY\\1", 14300)
  4. # Assign reaction set to reactor -- RXN_ID starts EMPTY (0 rows)!
     insert_row("DATA\\Blocks\\R-1\\Input\\RXN_ID")
     set_value("DATA\\Blocks\\R-1\\Input\\RXN_ID\\#0", "R-1")
  5. reinit_and_run()
  6. get_stream("R-OUT")            # Read outlet composition

KEY: RXN_ID is an empty table. You MUST insert_row BEFORE set_value,
or the \\#0 path will not exist and FindNode will fail.
This applies to both RPLUG and RCSTR.

For RStoic (block-level stoichiometry), use setup_block_reaction() instead.

Verification: Check COEF table after add_reaction.
If empty, see help("reaction-manual").
""",
        "deletion-order": """
# Deletion Order (CRITICAL)

Wrong order can CRASH the COM server. Follow exactly:

  Removing a block:
    1. list_block_ports("B1")         # Check which streams are connected
    2. disconnect("S1")               # Disconnect all streams first
       disconnect("S2")
    3. remove_block("B1")             # Then remove the block

  remove_block() now has built-in protection: if the block still
  has connected streams, it will REJECT the removal and tell you
  to disconnect() first. This prevents accidental COM crashes.

  disconnect() now uses a snapshot-first algorithm:
    1. Scans ALL blocks/ports to find where the stream lives
    2. Removes from ports one-by-one, collecting errors
    3. Only removes from Streams collection if port removals succeeded
    If port removals partially fail, the stream stays in Streams so
    remove_block() won't encounter an orphaned connection and crash.

  Removing a component:
    1. remove_component("WATER")      # Safe to remove directly
""",
        "com-recovery": """
# COM Recovery

When COM errors occur:

  1. Try: close_file() then open_file("your_simulation.apw")
     This fixes 90% of COM issues.

  2. If still broken: restart the MCP plugin / Reasonix.

  Common error patterns:
    - RPC_S_SERVER_UNAVAILABLE -> close_file() + open_file()
    - DISP_E_EXCEPTION / E_UNEXPECTED -> parameter error, retry is safe

  Tip: Don't mix MCP tools with external Python scripts
  that use win32com.client.Dispatch("Apwn.Document").
""",
        "stream-params": """
# Stream vs Block Parameters

  Block parameters:  set_param("B1", "TEMP", 100)
  Stream parameters: set_stream_param("S1", "TEMP", 100)

  DO NOT use set_param on streams -- it will fail.
  set_stream_param auto-handles the MIXED sub-node.

  Common stream params: TEMP (temperature), PRES (pressure),
                        TOTAL (total molar flow), VFRAC (vapor fraction)

  Both tools now auto-report unit hints:
    set_param("B1", "TEMP", 150)   -> "Set B1.TEMP = 150.0 [degC] range=(0.0, 5000.0)"
    set_stream_param("S1", "TEMP", 100) -> "Stream 'S1' TEMP = 100.0 [C]"

  Stream params expose .UnitString directly (e.g. "C", "bar", "kmol/hr").
  Block params use AttributeValue(3) for unit group codes.
""",
        "reaction-manual": """
# Manual Reaction Table Fill

If add_reaction() succeeds but the stoichiometry table is empty:

  COEF (reactants) -- fill manually:
    set_value("DATA\\Reactions\\Reactions\\R-1\\Input\\COEF\\1\\CO2\\MIXED", 1.0)
    set_value("DATA\\Reactions\\Reactions\\R-1\\Input\\COEF\\1\\H2\\MIXED", 4.0)

  COEF1 (products) -- fill manually:
    set_value("DATA\\Reactions\\Reactions\\R-1\\Input\\COEF1\\1\\CH4\\MIXED", 1.0)
    set_value("DATA\\Reactions\\Reactions\\R-1\\Input\\COEF1\\1\\H2O\\MIXED", 2.0)

  Need to add rows first? Use get_value / explore to check existing rows.
""",
        "component-facts": """
# Component TYPE Table

  The TYPE table has 2 columns:
    Column 0: Component label (e.g. "WATER")
    Column 1: Component type (Aspen auto-fills "CONV")

  Only column 0 needs to be set. DO NOT set column 1 manually --
  it will create a fake component row named "CONV".

  add_component() handles everything automatically.
""",
        "tips": """
# Quick Tips

  - batch_refresh(True) before bulk operations, batch_refresh(False) after
  - Use reinit_and_run() instead of run() after topology/parameter changes
  - probe() to diagnose COM health when things go wrong
  - visible(True) to show the Aspen GUI for visual debugging
  - explore("Data\\Blocks") to browse the simulation tree
  - diagnose(["convergence", "tolerance"]) for troubleshooting
  - flow sheet_topology() shows complete flow diagram (A --[stream]--> B)
  - list_tear_streams() / set_tear_estimate() for recycle loops
  - configure_fsplit() to split a stream into two products
  - new_simulation() auto-cleans template residuals -- starts truly empty
  - get_stream() shows "mole_frac_liq" and "mole_frac_vap" in the top result

Reactor quick reference:
  RStoic   -> setup_block_reaction() (block-level tables)
  RGIBBS   -> Just TEMP + PRES (no RXN_ID)
  RPLUG    -> add_reaction_set() + insert_row + set_value
  RCSTR    -> add_reaction_set() + insert_row + set_value

Reaction types for add_reaction_set(): POWERLAW, LHHW, GENERAL, EQUILIBRIUM.

New capabilities (via AttributeValue metadata):
  - find_incomplete_inputs() now shows Chinese descriptions + unit hints
  - validate_block(name) shows parameter diagnostics (active but unset)
  - set_param() auto-reports [unit] range=(min, max)
  - set_stream_param() auto-reports [unit] via .UnitString

See help("attribute-values") for the underlying metadata system.
""",
        "pitfalls": """
# Known Pitfalls

## 1. connect_port now APPENDS (not clear+add)
Multiple streams to the same port (e.g. MIXER F(IN)) work.
Just call connect_port multiple times.

## 2. Feed checking: 3-layer system
Layer 1 (pre-run): tool_run checks TEMP/PRES/composition on feed streams.
Layer 2 (post-run): convergence report shows BLKSTAT/PER_ERROR/BLKMSG.
Layer 3 (post-run): all-uncalculated fallback warning.

## 3. BLKSTAT meanings
0 = OK (normal success state). BLKSTAT=2 = not converged (ran but diverged).
1 = converged (success)
2 = not converged (ran but diverged)
3 = warning

## 4. RXN_ID requires insert_row first
RXN_ID is an empty table (0 rows). Always do:
    insert_row(r"\\Data\\Blocks\\R-1\\Input\\RXN_ID")
    set_value(r"\\Data\\Blocks\\R-1\\Input\\RXN_ID\\#0", "R-1")
This applies to both RPLUG and RCSTR.

## 5. _walk() vs FindNode()
_walk() uses Elements(name): works for static tree nodes.
  Fails for dynamic table rows (COEF\\\\1) because Elements("1") returns None.
FindNode("\\\\path") works everywhere, including dynamic rows.
  Path must start with backslash.

## 6. run() and reinit_and_run() have 30-second timeout
Internally these use Engine.Run() (async) + polling, so the COM thread
is never blocked. If the engine doesn't finish within 30 seconds,
Engine.Stop() is called and a TimeoutError is raised.
Feed stream checks (TEMP/PRES/composition) happen BEFORE the run,
so incomplete inputs are caught immediately without waiting.

## 7. SuppressDialogs stays True
Required to prevent hang from modal dialogs. Side effect: all Aspen
popup errors are suppressed. Use BLKMSG to read actual errors post-run.

## 8. Closure variable trap in aspen.call(impl)
The impl() function must NOT reassign variables from the outer scope.
Compute modified values BEFORE the closure, not inside it.

## 9. disconnect() safety (snapshot-first)
The old disconnect() removed from ports and Streams collection in one
pass, which could leave the stream orphaned if any removal failed.
Now it uses a 3-phase snapshot: scan all connections first, remove
from ports collecting errors, then clean up the Streams collection
only if all port removals succeeded.

## 10. flowsheet_topology() now shows full A--[stream]-->B format
Old version showed only half connections (E-1 --[stream--> without destination).
Now shows complete source --[stream]--> destination for every stream.

## 11. connect() now accepts source_port / dest_port
Use connect("SOURCE", "DEST", source_port="V(OUT)", dest_port="F(IN)")
for non-standard ports (e.g. FLASH2 vapor outlet).
Defaults are P(OUT) on source, F(IN) on destination -- same as before.
""",
        "dev-pattern": r"""
# Developer Guide: Writing COM-Safe Tool Functions

All COM objects (IHNode, IHapp) live on a dedicated apartment thread.
Tool functions MUST NOT access COM objects from the calling thread.

## Correct Pattern

Put ALL COM work inside an aspen.call(impl) lambda that returns only
plain Python data (str, int, float, list, dict, None):

    def tool_example(name: str) -> str:
        try:
            def impl():
                tree = aspen._app.RootModel("")
                node = _walk(tree, "Data", "Blocks", name, "Output")
                if node is None:
                    return "Not found"
                return str(node.Value)
            return aspen.call(impl)
        except Exception as exc:
            return f"Error: {exc}"

## Wrong Pattern

    node = aspen.get_node("Data", "Blocks", name)
    return node.Value

## _walk helper

    def _walk(root, *parts):
        node = root
        for p in parts:
            try:
                node = node.Elements(p)
            except Exception:
                return None
        return node

## Key rules

  1. Never access attributes of objects returned by get_node/find_node/root
     on the calling thread.
  2. Everything COM-related goes inside aspen.call().
  3. Return only plain data -- not COM wrappers.
  4. Use _walk() for static tree nodes, FindNode() for dynamic table rows.
  5. BLKSTAT: 0=OK, 1=converged, 2=not converged, 3=warning.
     BLKMSG has the actual Aspen error text.
  6. For 2D tables: use FindNode("\path\comp\substream").
     _walk() cannot navigate into dynamic table rows.
  7. Closure variables: capture values OUTSIDE impl() lambda.

RStoic 2D Table Pattern (for reference)
    els.InsertRow(0, 0)  # dim0 = component
    els.InsertRow(1, 0)  # dim1 = substream
    els.SetLabel(0, 0, False, "ETHANOL")
    els.SetLabel(1, 0, False, "MIXED")
    # Additional entries - SetLabel only (no InsertRow)
    els.SetLabel(0, 1, False, "ACETICAC")
    els.SetLabel(1, 1, False, "MIXED")
    # Values via FindNode
    node = root.FindNode("\Data\Blocks\R-1\Input\COEF\ETHANOL\MIXED")
    node.SetValue(0, -1.0)
""",
        "attribute-values": """
# AttributeValue(index) Complete Reference

Every parameter node in Aspen COM has index-based metadata via AttributeValue(int).
Decoded from actual COM reverse-engineering across multiple simulation files.

## Confirmed Index Meanings

  Index 0:  Parameter value itself (same as node.Value)
  Index 2:  Physical quantity code
            22 = temperature, 20 = pressure, 13 = heat duty,
            31 = temperature difference, 49 = specific heat,
            17 = diameter/length, 75 = pressure drop,
            11 = flow related, 0 = dimensionless/string enum
  Index 3:  Unit group code (depends on current Unit-Set per file)
            4 = degC, 5 = bar, 10 = kPa, 3 = Gcal/hr,
            18 = kW, 7 = m, 1 = m3/hr, 0 = dimensionless
  Index 5:  Option list node (IHNode), only for string-type params
  Index 7:  Active flag -- 1 = param is relevant in current config;
            0 = not applicable (e.g. FLASH_FORM on VALVE)
  Index 8:  Maximum allowed value
  Index 9:  Minimum allowed value
  Index 10: Default value (often 1e+35 = "unset placeholder")
  Index 11: User-set flag -- 1 = user has explicitly set this param;
            0 = not set (still default/empty)
  Index 18: Boolean flag (meaning unclear, always 0)
  Index 19: Chinese description string (very useful!)
            e.g. "出口温度。请参见帮助。" for TEMP
  Index 20: Boolean flag (meaning unclear, always 0)
  Index 22: Category/Group ID (Aspen UI page grouping, NOT engineering relevance)
            2 = TEMP + ENABLED + EO_FORM + ... (same UI page)
            3 = PRES + COMMENT + IVLOWER + ... (same UI page)
            TEMP and PRES are in DIFFERENT groups.

## What is NOT exposed via COM

  - "Red mark" (required indicator): NOT available. It's GUI-only logic.
  - Folder tooltip text ("输入不完整"): NOT available. GUI-only.
  - F4 / NextRequiredInput jump: NOT available via COM methods.

## Usage in Tools

  find_incomplete_inputs():        uses i7=1 + i11=0 + i19 for description
  set_param():                     uses i3 for unit hint, i8/i9 for range
  validate_block():                uses i7=1 + i11=0 + i19 for diagnostics
  _param_diagnostics():            uses i2+i3 for unit map, i7+i11+i19 for filtering

## Practical Note

  The unit hint map is keyed by (i2, i3):
    (22, 4) = degC    (20, 5) = bar    (20, 10) = kPa
    (13, 3) = Gcal/hr  (13, 18) = kW
    (31, 4) = degC     (49, 3) = kJ/kg-K
    (75, 5) = bar      (75, 18) = kPa
    (17, 3) = m        (11, 3) = kg/hr
""",
        "set-params": """
# Setting Parameters: Unit Hints & Diagnostics

Both set_param and set_stream_param now auto-report unit information.
This helps catch unit mismatch errors immediately.

## set_param (block parameters)

  set_param("B1", "TEMP", 150)
  -> "Set B1.TEMP = 150.0 [degC] range=(0.0, 5000.0)"

  The unit hint comes from AttributeValue(3) (unit group code).
  The range comes from AttributeValue(8)=max and AttributeValue(9)=min.
  These are Aspen's internal range limits, NOT engineering recommendations.

## set_stream_param (stream parameters)

  set_stream_param("S1", "TEMP", 100)
  -> "Stream 'S1' TEMP = 100.0 [C]"

  set_stream_param("S1", "PRES", 5)
  -> "Stream 'S1' PRES = 5.0 [bar]"

  Stream params expose .UnitString directly (unlike block params which
  use the indirect AttributeValue(3) code). This gives cleaner output.

## Common patterns

  Stream setup (always required before run):
    set_stream_param("FEED", "TEMP", 25)      # [C]
    set_stream_param("FEED", "PRES", 5)         # [bar]
    set_stream_composition("FEED", "WATER", 100) # kmol/hr

  Block setup (depends on SPEC_OPT):
    If SPEC_OPT='TP': set TEMP + PRES
    If SPEC_OPT='PV': set PRES + VFRAC
    If SPEC_OPT='TV': set TEMP + VFRAC
""",
        "diagnostics": """
# Parameter Diagnostics: Finding What's Missing

Three tools help diagnose incomplete simulations:

## 1. find_incomplete_inputs()
  Scans ALL blocks, uses smart categorization per block type:
  
  - Reads SPEC_OPT (operating mode) to determine which params are
    truly required vs optional in the current mode.
  - Groups output into Critical / Mode-irrelevant / Optional.
  - Skips ~200 infrastructure parameters automatically.

  Use this AFTER building topology but BEFORE running.

  Example output:
    [R-1 (ICON2)]  Current mode: SPEC_OPT=DUTY
        == Critical (needed for current mode) ==
        DUTY  -- 热负荷规定。  [Gcal/hr]
        -- Mode-irrelevant (needed if mode changes) --
        TEMP  -- 反应器出口温度。  [°C]
  
  Critical = must fill. Mode-irrelevant = can ignore (would matter only if SPEC_OPT changes).
  Optional = all other params, fill as needed.

## 2. validate_block(block_name)
  Focused on ONE block (quicker than full scan).
  Shows BLKSTAT + active but unset param diagnostics.

  Example output:
    Engine.Ready = True
    Block type = HEATER
    BLKSTAT = 0 (OK)
    Parameter diagnostics (active but unset):
        TEMP  -- 出口温度。请参见帮助。  [degC]

## 3. fill_trivial_params()
  Fills ~90+ infrastructure/UI-artifact params across all blocks
  with safe defaults (0 or ""). Run this once before using
  find_incomplete_inputs() to reduce noise from meaningless params.

## 4. diagnose(keywords)
  Full convergence report + knowledge base search.
  After a failed run, shows which blocks failed (BLKSTAT=2)
  plus parameter diagnostics for those blocks.

  diagnose(["HEATER", "TEMP"])  # Include keywords for knowledge base search

## Workflow

  1. Build topology
  2. fill_trivial_params()     -- clean up infrastructure noise
  3. find_incomplete_inputs()  -- see what truly needs filling
  4. Fill critical params (under "Critical" group)
  5. reinit_and_run()
  6. If fails: diagnose() or validate_block() + fix + re-run
""",
        "fill-trivial-params": """
# Fill Trivial Parameters

  fill_trivial_params()

  Fills ~90+ infrastructure/UI-artifact params across all blocks
  with safe defaults (0 for numbers, "" for strings).

  These are parameters that show up in find_incomplete_inputs() as
  "active but unset" because the COM metadata marks them as active
  (i7=1), but the user never needs to set them:

    - COM infrastructure (PSVBY, SSXML, THRU, etc.)
    - UI artifacts (PSVLABELBOX, PSVROUTE*, etc.)
    - Flash/estimation placeholders (P_EST, T_EST)
    - Dynamic holdup params (MEIN, MEOUT, V_IN, V_OUT)
    - Equation-oriented infrastructure (EOVAR_TYPE, EO_FORM, etc.)
    - Particle size distribution (OV_*, SUB_*, S_* parameters)

  Run it once before find_incomplete_inputs() to reduce noise.
  After running, find_incomplete_inputs() will only show the
  truly important missing parameters for your current simulation.
""",
    }


_init()


def get_help(topic: str | None = None) -> str:
    """Return help text for a topic, or list available topics."""
    if topic is None:
        topics = "\n".join(f"  - {k}" for k in sorted(HELP_TOPICS.keys()))
        return (
            "Available help topics:\n" + topics + "\n\n"
            "Usage: help(topic) -- e.g. help('workflow-from-scratch')"
        )
    topic = topic.lower().replace(" ", "-")
    if topic in HELP_TOPICS:
        return HELP_TOPICS[topic].strip()
    matches = [k for k in HELP_TOPICS if topic in k or k in topic]
    if matches:
        return HELP_TOPICS[matches[0]].strip()
    return f"Unknown topic '{topic}'. Use help() to list available topics."
