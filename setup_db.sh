#!/bin/bash
# Database download script for Render deployment

set -e

echo "Downloading Kilterboard database..."
echo "$KILTER_PASSWORD" | boardlib database kilter ./kilter.db --username "$KILTER_USERNAME"

if [ -f "./kilter.db" ]; then
    echo "Database downloaded successfully!"
    ls -lh kilter.db
else
    echo "ERROR: Database download failed"
    exit 1
fi
