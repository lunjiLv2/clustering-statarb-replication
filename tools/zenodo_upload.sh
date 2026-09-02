#!/bin/bash
# Upload the packaged data record to Zenodo straight from this machine (no download through VS Code).
#
#   1. zenodo.org -> your avatar -> Applications -> Personal access tokens -> New token,
#      scopes: deposit:write and deposit:actions. Copy it.
#   2. export ZENODO_TOKEN=...            (never paste the token into a file or a chat)
#   3. bash tools/zenodo_upload.sh runs/zenodo_out
#   The script creates a NEW draft deposition (a DOI is reserved at once), uploads every file in the
#   directory into its bucket, verifies each upload's MD5 against the local file, and prints the
#   draft's URL. Metadata (title, authors, licence CC BY 4.0, related GitHub identifier) and the final
#   Publish click are done in the browser on that draft page, so nothing irreversible happens here.
#   To use the Zenodo sandbox for a dry run: export ZENODO_HOST=https://sandbox.zenodo.org
set -euo pipefail
DIR="${1:?usage: zenodo_upload.sh <dir with the tar.gz files>}"
HOST="${ZENODO_HOST:-https://zenodo.org}"
: "${ZENODO_TOKEN:?export ZENODO_TOKEN first}"
command -v jq >/dev/null || { echo "jq not found; install-free fallback: python3 -c 'import sys,json;print(json.load(sys.stdin)[\"links\"][\"bucket\"])'"; }
j() { python3 -c "import sys,json; d=json.load(sys.stdin); print(eval('d'+sys.argv[1]))" "$1"; }
echo "creating draft deposition on $HOST ..."
resp=$(curl -sS -H "Authorization: Bearer $ZENODO_TOKEN" -H "Content-Type: application/json" -X POST "$HOST/api/deposit/depositions" -d '{}')
bucket=$(echo "$resp" | j "['links']['bucket']"); html=$(echo "$resp" | j "['links']['html']"); doi=$(echo "$resp" | j "['metadata']['prereserve_doi']['doi']")
echo "draft: $html"; echo "reserved DOI: $doi"
for f in "$DIR"/*.tar.gz "$DIR"/MANIFEST.csv "$DIR"/SHA256SUMS; do
  [ -f "$f" ] || continue; name=$(basename "$f"); echo "uploading $name ($(du -h "$f" | cut -f1)) ..."
  up=$(curl -sS --progress-bar -H "Authorization: Bearer $ZENODO_TOKEN" -X PUT "$bucket/$name" --upload-file "$f" | tee /dev/null)
  remote=$(echo "$up" | j "['checksum']" | sed 's/^md5://'); local=$(md5sum "$f" | cut -d' ' -f1)
  [ "$remote" = "$local" ] && echo "  ok  md5 $local" || { echo "  MD5 MISMATCH for $name: remote $remote local $local"; exit 1; }
done
echo; echo "All files uploaded and verified. Finish metadata + Publish at: $html"; echo "DOI to paste into README/CITATION.cff after publishing: $doi"
