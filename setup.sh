#!/bin/bash
# setup.sh - Run this once on your remote server

echo "🚀 Setting up admin tenant..."

# Make sure we're in the right directory
cd "$(dirname "$0")"

# Check if virtual environment exists, create if not
if [ ! -d "venv" ]; then
    echo "🔧 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Install/update dependencies if needed
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Run the admin tenant creation
echo "🏗️  Creating admin tenant..."
python3 create_admin_tenant.py

# Clean up the setup files (optional)
read -p "Remove setup files? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm create_admin_tenant.py
    rm setup.sh
    echo "🧹 Setup files removed"
fi

echo "✅ Setup complete!"
