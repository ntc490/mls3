#!/data/data/com.termux/files/usr/bin/bash
#
# MLS3 Startup Script for Termux
#
# Usage:
#   ./start.sh              # Run with production data
#   ./start.sh --debug-sms  # Run with SMS debug mode
#   ./start.sh --help       # Show help
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored messages
info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Parse arguments
DEBUG_SMS=false
SHOW_HELP=false

for arg in "$@"; do
    case $arg in
        --debug-sms)
            DEBUG_SMS=true
            shift
            ;;
        --help)
            SHOW_HELP=true
            shift
            ;;
        *)
            error "Unknown argument: $arg"
            SHOW_HELP=true
            ;;
    esac
done

if [ "$SHOW_HELP" = true ]; then
    echo "MLS3 Startup Script"
    echo ""
    echo "Usage:"
    echo "  ./start.sh              Run with production data"
    echo "  ./start.sh --debug-sms  Run with SMS debug mode (for testing)"
    echo "  ./start.sh --help       Show this help"
    echo ""
    exit 0
fi

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

info "Starting MLS3..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    error "Virtual environment not found. Please run setup first:"
    echo "  python -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi

# Check if data directory is configured
if [ -z "$MLS3_DATA_DIR" ]; then
    warn "MLS3_DATA_DIR not set. Using default: ./data"
    warn "To use production data, set: export MLS3_DATA_DIR=/path/to/your/data"
else
    info "Using data directory: $MLS3_DATA_DIR"
fi

# Set debug mode if requested
if [ "$DEBUG_SMS" = true ]; then
    export MLS3_DEBUG_SMS=true
    warn "SMS debug mode enabled - SMS will not actually be sent"
fi

# Activate virtual environment
info "Activating virtual environment..."
source venv/bin/activate

# Check for termux-open-url if not in debug mode
if [ "$DEBUG_SMS" = false ]; then
    if ! command -v termux-open-url &> /dev/null; then
        error "termux-open-url not found!"
        echo "Please install termux-api:"
        echo "  pkg install termux-api"
        echo ""
        echo "Also install Termux:API from F-Droid"
        exit 1
    fi
fi

# Display startup info
echo ""
info "MLS3 Configuration:"
echo "  Data Directory: ${MLS3_DATA_DIR:-./data}"
echo "  SMS Debug Mode: $DEBUG_SMS"
echo "  Port: 5000"
echo ""

# Start the app
info "Starting Flask application..."
echo ""
python app.py

# This runs if app is stopped
info "MLS3 stopped"
