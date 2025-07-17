#!/bin/bash
# setup.sh - Run this once on your remote server

echo "🚀 Setting up admin tenant..."

# Make sure we're in the right directory
cd "$(dirname "$0")"

# Install/update dependencies if needed
echo "📦 Installing dependencies..."
pip3 install -r requirements.txt

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
