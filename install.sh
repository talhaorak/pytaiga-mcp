#!/bin/bash

# Check if dev dependencies should be installed
if [ "$1" = "--dev" ]; then
    echo "Installing with development dependencies..."
    uv pip install -e ".[dev]"
else
    echo "Installing production dependencies..."
    uv pip install -e .
fi