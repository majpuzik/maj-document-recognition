#!/bin/bash
# MAJ Document Recognition - Quick Install Script

set -e

echo "=========================================="
echo "MAJ Document Recognition - Installation"
echo "=========================================="
echo ""

# Check Python version
echo "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "Found Python $PYTHON_VERSION"

if [[ $(echo "$PYTHON_VERSION < 3.8" | bc -l) -eq 1 ]]; then
    echo "Error: Python 3.8+ is required"
    exit 1
fi

# Check Tesseract
echo ""
echo "Checking Tesseract OCR..."
if ! command -v tesseract &> /dev/null; then
    echo "Warning: Tesseract OCR not found"
    echo "Please install it:"
    echo "  macOS:   brew install tesseract"
    echo "  Ubuntu:  sudo apt-get install tesseract-ocr"
    echo "  Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    TESSERACT_VERSION=$(tesseract --version | head -n1)
    echo "Found $TESSERACT_VERSION"
fi

# Create virtual environment
echo ""
echo "Creating virtual environment..."
if [ -d "venv" ]; then
    echo "Virtual environment already exists"
    read -p "Recreate? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf venv
        python3 -m venv venv
    fi
else
    python3 -m venv venv
fi

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip setuptools wheel

# Install package
echo ""
echo "Installing MAJ Document Recognition..."
read -p "Install with development dependencies? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    pip install -e ".[dev]"
else
    pip install -e .
fi

# Create directories
echo ""
echo "Creating data directories..."
mkdir -p data/{uploads,temp,cache}
mkdir -p logs
mkdir -p config

# Copy example config
echo ""
echo "Copying example configuration..."
if [ ! -f "config/paperless_config.json" ]; then
    cp config/paperless_config.example.json config/paperless_config.json
    echo "Created config/paperless_config.json"
fi

# Generate secret key
echo ""
echo "Generating secret key for web application..."
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
echo "Secret key: $SECRET_KEY"
echo "Add this to config/config.yaml under web.secret_key"

# Test installation
echo ""
echo "Testing installation..."
if python3 -c "import src; print('✓ Package imported successfully')"; then
    echo "✓ Installation successful"
else
    echo "✗ Installation failed"
    exit 1
fi

# Print next steps
echo ""
echo "=========================================="
echo "Installation completed successfully!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Edit config/config.yaml with your settings"
echo "2. If using Paperless-NGX, add API token to config/paperless_config.json"
echo "3. Run: source venv/bin/activate"
echo "4. Test: maj-docrecog --help"
echo "5. Start web GUI: maj-docrecog-web"
echo ""
echo "Documentation: docs/README.md"
echo "Examples: examples/"
echo ""
echo "Enjoy! 🎉"
