#!/bin/bash

# Help/usage function
show_help() {
    echo "Usage: ./inspect.sh [OPTIONS]"
    echo
    echo "Inspect the Taiga MCP server using the MCP Inspector tool"
    echo
    echo "Options:"
    echo "  --sse            Use SSE transport mode (default is stdio)"
    echo "  --dev            Run in development mode with mock data"
    echo "  -h, --help       Show this help message"
    echo
    echo "Examples:"
    echo "  ./inspect.sh                  # Inspect with stdio transport"
    echo "  ./inspect.sh --sse            # Inspect with SSE transport"
    echo "  ./inspect.sh --dev            # Inspect with stdio in dev mode"
    echo "  ./inspect.sh --sse --dev      # Inspect with SSE in dev mode"
}

# Default values
TRANSPORT_MODE=""
DEV_MODE=""

# Parse command line arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --sse) TRANSPORT_MODE="--sse"; shift ;;
        --dev) DEV_MODE="TAIGA_DEV_MODE=true"; shift ;;
        -h|--help) show_help; exit 0 ;;
        *) echo "Unknown parameter: $1"; show_help; exit 1 ;;
    esac
done

echo "Starting MCP Inspector for Taiga MCP server..."

if [ -n "$DEV_MODE" ]; then
    echo "Running in development mode with mock data"
fi

echo "Transport mode: ${TRANSPORT_MODE:-stdio (default)}"
echo

# Run the MCP Inspector with the appropriate command
if [ -n "$DEV_MODE" ]; then
    # With development mode
    npx -y @modelcontextprotocol/inspector $DEV_MODE python src/server.py $TRANSPORT_MODE
else
    # Without development mode
    npx -y @modelcontextprotocol/inspector python src/server.py $TRANSPORT_MODE
fi 