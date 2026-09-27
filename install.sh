#!/usr/bin/env bash
# Install or update Modlock Tools:
#   curl -fsSL https://raw.githubusercontent.com/paralin/modlock-sdk/master/install.sh | bash
# Set MODLOCK_TOOLS_DIR to choose the directory (default ~/modlock-tools).
set -euo pipefail

main() {
  local destination="${MODLOCK_TOOLS_DIR:-$HOME/modlock-tools}"
  local ref="${MODLOCK_TOOLS_REF:-master}"
  local source="$destination/.cache/source"

  if ! command -v uv >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
  fi

  rm -rf "$source"
  mkdir -p "$source"
  curl -fsSL "https://github.com/paralin/modlock-sdk/archive/$ref.tar.gz" |
    tar -xz --strip-components=1 -C "$source"
  uv run --no-project --python 3.14 "$source/scripts/install.py" --destination "$destination" "$@"
}

main "$@"
