#!/bin/zsh
cd "$(dirname "$0")"
if ./start_image_pipeline.sh restart-core; then
  open -a "Brave Browser" "http://127.0.0.1:3001/"
else
  echo "Core services did not become ready; Brave was not opened." >&2
  exit 1
fi
