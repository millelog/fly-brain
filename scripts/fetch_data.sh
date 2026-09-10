#!/usr/bin/env bash
# Downloads the three data files into data/. Idempotent.
set -euo pipefail
cd "$(dirname "$0")/../data"
E=https://raw.githubusercontent.com/eonsystemspbc/fly-brain/main/data
A=https://raw.githubusercontent.com/flyconnectome/flywire_annotations/main/supplemental_files
for u in $E/2025_Completeness_783.csv $E/2025_Connectivity_783.parquet $A/Supplemental_file1_neuron_annotations.tsv; do
  [ -f "$(basename $u)" ] || curl -fL# -O "$u"
done
ls -la
