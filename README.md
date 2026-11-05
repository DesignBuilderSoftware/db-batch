# db-batch

A tool to run a batch of [DesignBuilder](https://designbuilder.co.uk/) files automatically and
collect their output files.

It drives the DesignBuilder GUI application itself (via
[`db-process`](https://github.com/DesignBuilderSoftware/db-process)) rather than a headless
simulation engine, so a model open in DesignBuilder counts as "running" the same way it would if
you'd started it by hand.

## Prerequisites

- Windows
- A licensed DesignBuilder installation
- Python >=3.10

## Installation

The project is managed with [uv](https://docs.astral.sh/uv/):

```bash
uv sync
```

This also installs [`db-process`](https://github.com/DesignBuilderSoftware/db-process), which is
pulled from a pinned git revision rather than PyPI.

## Usage

```bash
uv run run_db_batch <modelsDirOrFile> <outputsDir>
```

- `modelsDirOrFile` - a directory containing `.dsb` models (optionally nested, see
  `--nSubDirs`), or a single `.dsb` file.
- `outputsDir` - directory where collected output files are written.

Run `uv run run_db_batch --help` for the full list of options. The ones you're most likely to
need:

| Option                          | Description                                                          |
| -------------------------------- | ---------------------------------------------------------------------|
| `--analysis {sbem,eplus,none}`   | Analysis type to run (default `sbem`) - see below.                   |
| `--timeout SECONDS`              | Per-model timeout before DesignBuilder is killed (default `300`).    |
| `--nSubDirs N`                   | Look for `.dsb` files up to `N` levels deep (default `1`).           |
| `--startIndex N` / `--endIndex N`| Run only models `N` through `M` of the batch, e.g. to resume a part-finished run. |
| `--report`                       | Write a summary report to `outputsDir` (see below).                  |

### Analysis types

- `sbem` - runs an SBEM calculation.
- `eplus` - runs an EnergyPlus simulation.
- `none` - only updates each model (applies `--changeAttr`, sim dates, etc.) without triggering a
  calculation.
- `dsm` is recognised by a couple of internal lookups but raises `NotImplementedError` - it is not
  supported.

### Collected output files

For each model, a default set of output files is copied from DesignBuilder's app data directory
into `outputsDir`:

- `sbem`: `model.inp`, `model_epc.inp` and its PDF variants, `model_ber.inp` and its PDF variants.
- `eplus`: `in.idf`, `eplusout.err`, `eplusout.eso`, `eplustbl.htm`.

Naming and layout of the copied files is controlled by:

- `--outputSubDirs` - create a results subdirectory per model, instead of a flat output directory.
- `--noModelNames` - don't include the model name in copied file titles.
- `--originalNames` - include the model's original (in-DesignBuilder) name in copied file titles.

### Summary report

Passing `--report` writes a `summary_<analysis>_<timestamp>.txt` file to `outputsDir`, listing how
many models ended up in each of:

- **Skipped** - outside the `--startIndex`/`--endIndex` range.
- **Timeout expired** - DesignBuilder was still active when `--timeout` elapsed and was killed.
- **Failed** - completed without producing the expected result (currently only tracked for
  `eplus`).
- **Successful** - completed normally.

## Behaviour to be aware of

- **Only one DesignBuilder instance is allowed to run at a time.** Before each model, any running
  DesignBuilder process is killed - including one you have open yourself. Don't run a batch while
  you have DesignBuilder open with unsaved work.
- Models are run **sequentially**, one at a time. A model that hangs is bounded by `--timeout`
  rather than blocking the batch indefinitely.

## Reading SBEM results

[`db_batch.reader`](db_batch/reader) reads SBEM `model_epc.inp` / `model_ber.inp` result files
into a pandas `DataFrame`, for comparing outputs across a batch of models:

```python
from db_batch.reader.sbem_reader import SbemRequest, get_results

request = SbemRequest(
    "ACTUAL - BUILDING-DATA",
    "BUILDING_DATA",
    ["KWH/M2-HEAT", "KWH/M2-COOL", "KWH/M2-AUX", "KWH/M2-LIGHT", "KWH/M2-DHW", "KWH/M2-EQUP"],
)
df = get_results(["path/to/model_epc.inp", ...], request)
```

See [`db_batch/reader/read_batch.py`](db_batch/reader/read_batch.py) for a fuller worked example.

## Development

```bash
uv sync
```

installs the `dev` dependency group ([pre-commit](https://pre-commit.com/), pylint, pytest,
ruff). Common tasks are wrapped in [`just`](https://github.com/casey/just) recipes:

```bash
just lint    # ruff check
just check   # pytest
just update  # uv sync --upgrade
```

Pre-commit hooks (`ruff-check`, `ruff-format`, `pylint`) run automatically once installed:

```bash
uv run pre-commit install
```

There are currently no tests, so `just check` collects nothing.
