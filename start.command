#!/bin/zsh
cd "$(dirname "$0")"
exec ./start_image_pipeline.sh restart-core
