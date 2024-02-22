#!/bin/bash
set -e

echo "Cleaning previous builds..."
rm -rf ./dist

echo "Activating conda environment..."
. /Users/i824113/miniconda3/etc/profile.d/conda.sh
conda deactivate
conda activate gptextual

echo "Building..."
python3 -m build

echo "Uploading..."
twine upload ./dist/*

echo "Build and upload process completed successfully."