#!/usr/bin/env bash
# Model-check the claims protocol: bash scripts/tla_check.sh [docs/tla/Claims.cfg]
# Exits 0 when TLC finds no error, non-zero on a violation (docs/tla/ClaimsBroken.cfg must give one).
# Needs Java ($JAVA or java on PATH). The jar is downloaded once into $UAK_TLA_CACHE and checked against its pin.
set -eu

TLA_VERSION=1.7.4
TLA_SHA256=936a262061c914694dfd669a543be24573c45d5aa0ff20a8b96b23d01e050e88

here=$(cd "$(dirname "$0")/.." && pwd -P)
cfg=${1:-$here/docs/tla/Claims.cfg}
cache=${UAK_TLA_CACHE:-$HOME/.cache/uak-tla}
jar="$cache/tla2tools-$TLA_VERSION.jar"

sha256() { if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1"; else shasum -a 256 "$1"; fi | awk '{print $1}'; }

mkdir -p "$cache"
if [ ! -f "$jar" ]; then
  curl -fsSL -o "$jar.part" "https://github.com/tlaplus/tlaplus/releases/download/v$TLA_VERSION/tla2tools.jar"
  mv "$jar.part" "$jar"
fi
got=$(sha256 "$jar")
if [ "$got" != "$TLA_SHA256" ]; then
  rm -f "$jar"
  echo "tla_check: SHA-256 mismatch for tla2tools $TLA_VERSION: got $got, pinned $TLA_SHA256" >&2
  exit 2
fi

meta=$(mktemp -d)
trap 'rm -rf "$meta"' EXIT
cd "$(dirname "$cfg")"
# X.cfg checks X.tla when it exists (ClaimsPerAgent.cfg); variants of the main model (ClaimsBroken.cfg) check Claims.tla.
spec=$(basename "$cfg" .cfg).tla
[ -f "$spec" ] || spec=Claims.tla
# -deadlock: a finished run (clock at MaxTime, budgets spent) is not an error.
"${JAVA:-java}" -XX:+UseParallelGC -cp "$jar" tlc2.TLC -deadlock -workers auto -metadir "$meta" \
  -config "$(basename "$cfg")" "$spec"
