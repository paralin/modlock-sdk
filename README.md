# Modlock SDK reconstruction

Tools for inspecting a community SDK and assembling explicit file selections
from identified source trees. Requires Python 3.11 or newer, with no third-party
Python packages.

The complete Valve depot recipe is still unresolved. These scripts do not
download depots, authenticate to Steam, or execute the community binaries.

## Inventory the reference

```sh
uv run --no-project python scripts/sdk_inventory.py zip \
  ../modlock-sdk-inputs/Reduced_CSDK_12.zip \
  --strip-prefix Reduced_CSDK_12/ > reference.json
```

`directory <root>` inventories an isolated source tree. `compare <reference>
<source-inventory>...` finds all byte-identical matches, including renamed files,
while leaving unmatched entries explicit. Source acquisition records establish
provenance; hash matches alone do not authenticate a publisher.

## Assemble a reviewed recipe

```sh
uv run --no-project python scripts/assemble_sdk.py recipe.json /path/to/new-sdk
```

A recipe declares `sources` by name, each with a `root`, and a nonempty `files`
array. Each file selects `source`, `from`, `to`, and the expected `sha256`.
Keep the actual Valve app, depot, and manifest with each source declaration.
Configuration replacements can come from a separate reviewed source tree.

Assembly requires a new destination and validates every selected file's hash.
It rejects traversal, duplicate Windows output names, and changed source bytes.
It does not resolve a compiler's dependency set or prove that the result runs.

The maintained guide and script copies are in
`/Users/cjs/deadlock/guides/modlock-sdk-assembly.org` and its `.d/` directory.
That guide records the archive inventory, known contradictions, source
references, recipe format, and remaining verification.
