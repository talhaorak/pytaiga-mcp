#!/bin/bash

# Check if transport mode is provided as an argument
if [ "$1" == "--sse" ]; then
    # Use SSE transport
    uv run python src/server.py --sse
else
    # Default to stdio transport
    uv run python src/server.py
fi