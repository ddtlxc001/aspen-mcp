> **Note:** Code examples in this file reference internal COM tree operations (`insert_row`, `set_label`, etc.) — not the user-facing MCP tools. See the main README for the MCP tool interface.

# RadFrac (Rigorous Distillation)

Rigorous multi-stage vapor-liquid fractionation column with condenser and reboiler.

## Ports

| Port | Direction | Type |
|------|-----------|------|
| F | IN | Feed (multiple feeds allowed) |
| HS | IN | Heat stream |
| VD | OUT | Vapor distillate |
| LD | OUT | Liquid distillate |
| B | OUT | Bottoms |
| SP | OUT | Side product |
| WD | OUT | Water decant |
| CHS | OUT | Condenser heat stream |
| RHS | OUT | Reboiler heat stream |
| PS | OUT | Pseudo stream |

## Input

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\NSTAGE` | int | Number of stages |
| `\Data\Blocks\{name}\Input\CONDENSER` | string | `TOTAL`, `PARTIAL-V`, `PARTIAL-V-L`, `NONE` |
| `\Data\Blocks\{name}\Input\REBOILER` | string | `KETTLE`, `THERMOSIPHON`, `NONE` |
| `\Data\Blocks\{name}\Input\NO_PHASE` | int | Number of phases |
| `\Data\Blocks\{name}\Input\BASIS_RR` | float | Specified reflux ratio |
| `\Data\Blocks\{name}\Input\BASIS_BR` | float | Specified boilup ratio |
| `\Data\Blocks\{name}\Input\BASIS_D` | float | Specified distillate rate |
| `\Data\Blocks\{name}\Input\BASIS_B` | float | Specified bottoms rate |
| `\Data\Blocks\{name}\Input\BASIS_VN` | float | Specified boilup rate |
| `\Data\Blocks\{name}\Input\D:F` | float | Distillate-to-feed ratio |
| `\Data\Blocks\{name}\Input\B:F` | float | Bottoms-to-feed ratio |
| `\Data\Blocks\{name}\Input\QN` | float | Reboiler duty |
| `\Data\Blocks\{name}\Input\QC` | float | Condenser duty |
| `\Data\Blocks\{name}\Input\FEED_STAGE\{stream}` | int | Feed stage for a stream |
| `\Data\Blocks\{name}\Input\FEED_CONVEN\{stream}` | string | Feed convention: `ABOVE-STAGE`, `ON-STAGE` |
| `\Data\Blocks\{name}\Input\PRES1` | float | Top stage pressure |
| `\Data\Blocks\{name}\Input\STAGE_PRES\1` | float | Top stage pressure (alternative path) |
| `\Data\Blocks\{name}\Input\DP_STAGE` | float | Pressure drop per stage |
| `\Data\Blocks\{name}\Input\CALC_MODE` | string | Calculation mode: `EQUILIBRIUM` (default), `RIG-RATE` (rate-based) |

> RadFrac requires exactly **2 operating specs**. Common combinations:
> - Reflux ratio (`BASIS_RR`) + Boilup ratio (`BASIS_BR`)
> - Reflux ratio (`BASIS_RR`) + Distillate rate (`BASIS_D`)
> - Reflux ratio (`BASIS_RR`) + Bottoms rate (`BASIS_B`)

> **You must clear one spec before setting another.** For example, to switch from boilup ratio to reboiler duty, first clear `BASIS_BR`, then set `QN`.

## Output

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Output\MOLE_RR` | float | Calculated molar reflux ratio |
| `\Data\Blocks\{name}\Output\MOLE_D` | float | Calculated distillate rate |
| `\Data\Blocks\{name}\Output\MOLE_B` | float | Calculated bottoms rate |
| `\Data\Blocks\{name}\Output\MOLE_VN` | float | Calculated boilup rate |
| `\Data\Blocks\{name}\Output\BU_RATIO` | float | Calculated molar boilup ratio |
| `\Data\Blocks\{name}\Output\MASS_BR` | float | Calculated mass boilup ratio |
| `\Data\Blocks\{name}\Output\TOP_TEMP` | float | Condenser / top stage temperature |
| `\Data\Blocks\{name}\Output\PRES1` | float | Condenser / top stage pressure |
| `\Data\Blocks\{name}\Output\COND_DUTY` | float | Condenser heat duty |
| `\Data\Blocks\{name}\Output\SCDUTY` | float | Condenser subcooled duty |
| `\Data\Blocks\{name}\Output\MOLE_L1` | float | Condenser reflux rate |
| `\Data\Blocks\{name}\Output\RW` | float | Free water reflux ratio |
| `\Data\Blocks\{name}\Output\REB_POUT` | float | Reboiler pressure |
| `\Data\Blocks\{name}\Output\REB_TOUT` | float | Reboiler temperature |
| `\Data\Blocks\{name}\Output\REB_DUTY` | float | Reboiler heat duty |

## Side Duties

Use `add_side_duty` tool or manual path:
```
\Data\Blocks\{name}\Input\HEATER_DUTY\{stage}
```
Side duties are rejected on condenser (stage 1) and reboiler (last stage).

## Typical Setup

**Using MCP tools (recommended):**
```
set_column_stages("C1", 20)
set_condenser_type("C1", "TOTAL")
set_column_specs("C1", rr=2.0, d=50.0)    # reflux ratio + distillate
set_feed_stage("C1", "FEED", 10)
set_column_pressure("C1", 1.0)
```

**Using COM paths directly:**
```
set_value(r"\Data\Blocks\C1\Input\NSTAGE", 20)
set_value(r"\Data\Blocks\C1\Input\CONDENSER", "TOTAL")
set_value(r"\Data\Blocks\C1\Input\BASIS_RR", 2)
set_value(r"\Data\Blocks\C1\Input\BASIS_D", 50)
set_value(r"\Data\Blocks\C1\Input\FEED_STAGE\FEED", 10)
set_value(r"\Data\Blocks\C1\Input\PRES1", 1.0)
```

`set_column_specs` accepts exactly 2 of: `rr` (BASIS_RR), `d` (BASIS_D), `b` (BASIS_B), `br` (BASIS_BR).
It automatically clears old specs before setting new ones.

## Gotchas

- Max 2 operating specs — setting a 3rd will cause errors.
- `PARTIAL-V` condenser: top product exits from VD(OUT) port (vapor distillate).
- `TOTAL` condenser: top product exits from LD(OUT) port (liquid distillate).
- Feed stage numbered from top (condenser = stage 1).
- For column with `REBOILER=NONE` and N stages, bottom feed goes to stage N+1.
- "COLUMN DRIES UP" error = wrong feed conditions or impossible specs.
- For absorber configuration (`CONDENSER=NONE`, `REBOILER=NONE`): the bottom gas feed must be placed at stage **N+1** (e.g., stage 11 for a 10-stage absorber). Placing it at stage N will cause `check_inputs` to report incomplete.
- `WD(OUT)` port (water decant) is not in the standard port definitions. `connect_stream` will fuzzy-match `WD` to `VD` incorrectly. Use `add_element` directly instead:
  ```
  add_element(session, '\Data\Blocks\COL1\Ports\WD(OUT)", "STREAM_NAME')
  ```
  To disconnect, use `# Internal: remove_element at \Data\Blocks\COL1\Ports\WD(OUT), name=STREAM_NAME`.
- `BLKOPFREWAT` (free-water): once set to `YES`, it cannot be changed back to `NO` due to coupled internal settings. The only way to revert is to `remove_block` and recreate.
- Columns with immiscible components (e.g., VAM-water, organic-water) require 3-phase (`NO_PHASE=3`) or free-water (`BLKOPFREWAT=YES`) mode. Running in 2-phase mode will cause non-convergence or "COLUMN DRIES UP" errors.
- Liquid feeds from high-pressure separators may contain dissolved light gases (C₂H₄, CO₂, etc.). Add a Flash2 degassing step before the column, otherwise the dissolved gases will dominate the distillate and cause "column dries up" on stripping stages.
