# Compr (Compressor / Turbine)

Single-stage compressor or turbine for gas compression or expansion.

## Ports

| Port | Direction | Type |
|------|-----------|------|
| F | IN | Feed |
| WS | IN | Work stream in |
| P | OUT | Product |
| WD | OUT | Work duty out |
| WS | OUT | Work stream out |

## Input

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Input\TYPE` | string | Model type: `ISENTROPIC`, `POLYTROPIC`, `POSITIVE-DIS` |
| `\Data\Blocks\{name}\Input\OPT_SPEC` | string | Spec type — **must set first**: `PRES`, `TEMP`, `POWER`, `PRATIO` |
| `\Data\Blocks\{name}\Input\PRES` | float | Discharge pressure (when OPT_SPEC=PRES) |
| `\Data\Blocks\{name}\Input\DELP` | float | Pressure increase (when OPT_SPEC=DELP) |
| `\Data\Blocks\{name}\Input\PRATIO` | float | Pressure ratio (when OPT_SPEC=PRATIO) |
| `\Data\Blocks\{name}\Input\POWER` | float | Power (when OPT_SPEC=POWER) |
| `\Data\Blocks\{name}\Input\TEMP` | float | Discharge temperature (when OPT_SPEC=TEMP) |
| `\Data\Blocks\{name}\Input\SEFF` | float | Isentropic efficiency (0–1) |
| `\Data\Blocks\{name}\Input\PEFF` | float | Polytropic efficiency (0–1) |
| `\Data\Blocks\{name}\Input\MEFF` | float | Mechanical efficiency (0–1) |

> **Important:** Set `OPT_SPEC` before setting the discharge value — without it, the block stays incomplete.

> Efficiency type must match TYPE: ISENTROPIC → `SEFF`, POLYTROPIC / POSITIVE-DIS → `PEFF`.

## Output

| Path | Type | Description |
|------|------|-------------|
| `\Data\Blocks\{name}\Output\IND_POWER` | float | Indicated horsepower |
| `\Data\Blocks\{name}\Output\BRAKE_POWER` | float | Calculated brake horsepower |
| `\Data\Blocks\{name}\Output\WNET` | float | Net work required |
| `\Data\Blocks\{name}\Output\POWER_LOSS` | float | Power loss |
| `\Data\Blocks\{name}\Output\EPC` | float | Efficiency used (polytropic or isentropic) |
| `\Data\Blocks\{name}\Output\POC` | float | Calculated discharge pressure |
| `\Data\Blocks\{name}\Output\DELP_CAL` | float | Calculated pressure change |
| `\Data\Blocks\{name}\Output\PRES_RATIO` | float | Calculated pressure ratio |
| `\Data\Blocks\{name}\Output\TOC` | float | Outlet temperature |
| `\Data\Blocks\{name}\Output\TOS` | float | Isentropic outlet temperature |
| `\Data\Blocks\{name}\Output\B_VFRAC` | float | Vapor fraction |
| `\Data\Blocks\{name}\Output\HEAD_CAL` | float | Head developed |
| `\Data\Blocks\{name}\Output\FEED_VFLOW` | float | Inlet volumetric flow rate |
| `\Data\Blocks\{name}\Output\VFLOW` | float | Outlet volumetric flow rate |

## Typical Setup

```
add_block("COMP1", "COMPR")
set_value(r"\Data\Blocks\COMP1\Input\TYPE", "ISENTROPIC")
set_value(r"\Data\Blocks\COMP1\Input\OPT_SPEC", "PRES")
set_value(r"\Data\Blocks\COMP1\Input\PRES", 30)
set_value(r"\Data\Blocks\COMP1\Input\SEFF", 0.75)
```

## Gotchas

- **Must set OPT_SPEC before setting the outlet value** — without it, the block stays incomplete.
- Efficiency type must match compressor TYPE:
  - ISENTROPIC → `SEFF`
  - POLYTROPIC / POSITIVE-DIS → `PEFF`
- Setting the wrong efficiency type leaves the block incomplete.
- For liquid pumping, use the Pump block instead.
