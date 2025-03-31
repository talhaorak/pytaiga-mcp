#!/bin/bash
# Usage examples:
# stdio mode: 
#   npx -y @modelcontextprotocol/inspector uv --directory /Users/talhaorak/Codes/pyTaigaMCP2 run python src/server.py --mode stdio --log-level [DEBUG|INFO|ERROR](default INFO) --log-file <log filename. default server.log>
# sse mode:
#   npx -y @modelcontextprotocol/inspector uv --directory /Users/talhaorak/Codes/pyTaigaMCP2 run python src/server.py --mode sse --port 5001 --log-level [DEBUG|INFO|ERROR](default INFO) --log-file <log filename. default server.log>


# Help/usage function
show_help() {
    echo "Usage: ./inspect.sh [OPTIONS]"
    echo "Options:"
    echo "  --mode <stdio|sse>       Specify the mode to run the command in (default: stdio)."
    echo "  --port <port>           Specify the port to run the command on (default: 5001)."
    echo "  --log-level <level>     Specify the log level (default: INFO)."
    echo "  --log-file <filename>   Specify the log file name (default: server.log)."
    echo "  --help                  Show this help message."
    echo "  --version               Show the version information."
    echo ""
    echo "Examples:"
    echo "  ./inspect.sh"
    echo "  ./inspect.sh --mode stdio --log-level DEBUG --log-file my_log.log"
    echo "  ./inspect.sh --mode sse --port 5001 --log-level ERROR"
}

# Default values
MODE="stdio"
PORT=5001
LOG_LEVEL="INFO"
LOG_FILE="server.log"
VERSION="1.0.0"

# Absolute path of current script
DIRECTORY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"


# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --mode)
            MODE="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --log-level)
            LOG_LEVEL="$2"
            shift 2
            ;;
        --log-file)
            LOG_FILE="$2"
            shift 2
            ;;
        --help)
            show_help
            exit 0
            ;;
        --version)
            echo "Version: $VERSION"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done
# Check if the mode is valid
if [[ "$MODE" != "stdio" && "$MODE" != "sse" ]]; then
    echo "Invalid mode: $MODE"
    show_help
    exit 1
fi
# Check if the log level is valid
if [[ "$LOG_LEVEL" != "DEBUG" && "$LOG_LEVEL" != "INFO" && "$LOG_LEVEL" != "ERROR" ]]; then
    echo "Invalid log level: $LOG_LEVEL"
    show_help
    exit 1
fi
# Check if the log file is valid
if [[ -z "$LOG_FILE" ]]; then
    echo "Invalid log file: $LOG_FILE"
    show_help
    exit 1
fi
# Check if the port is valid
if ! [[ "$PORT" =~ ^[0-9]+$ ]]; then
    echo "Invalid port: $PORT"
    show_help
    exit 1
fi
# Check if the port is in the valid range
if [[ "$PORT" -lt 1024 || "$PORT" -gt 65535 ]]; then
    echo "Port must be between 1024 and 65535: $PORT"
    show_help
    exit 1
fi

# Run the command with the specified options
if [[ "$MODE" == "stdio" ]]; then
    echo "Running in stdio mode..."
    # Add your command here
    # Example: python src/server.py --mode stdio --log-level $LOG_LEVEL --log-file $LOG_FILE
    npx -y @modelcontextprotocol/inspector uv --directory $DIRECTORY run python src/server.py --mode stdio --log-level $LOG_LEVEL --log-file $LOG_FILE
elif [[ "$MODE" == "sse" ]]; then
    echo "Running in sse mode..."
    # Add your command here
    # Example: python src/server.py --mode sse --port $PORT --log-level $LOG_LEVEL --log-file $LOG_FILE
    npx -y @modelcontextprotocol/inspector uv --directory $DIRECTORY run python src/server.py --mode sse --log-level $LOG_LEVEL --log-file $LOG_FILE --port $PORT
fi
