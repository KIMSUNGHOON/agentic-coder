#!/bin/bash
# Increase system file watcher limit to prevent ENOSPC errors
# This script increases the inotify max_user_watches limit

set -e

echo "========================================="
echo "File Watcher Limit Increase Script"
echo "========================================="
echo ""

# Check current limit
CURRENT_LIMIT=$(cat /proc/sys/fs/inotify/max_user_watches 2>/dev/null || echo "8192")
echo "Current limit: $CURRENT_LIMIT"

# Recommended limit for large projects
RECOMMENDED_LIMIT=524288

echo "Recommended limit: $RECOMMENDED_LIMIT"
echo ""

if [ "$CURRENT_LIMIT" -ge "$RECOMMENDED_LIMIT" ]; then
    echo "✅ Current limit ($CURRENT_LIMIT) is already sufficient"
    exit 0
fi

echo "⚠️  Current limit is too low. Increasing to $RECOMMENDED_LIMIT..."
echo ""

# Check if running with sudo
if [ "$EUID" -ne 0 ]; then
    echo "❌ This script needs sudo privileges to modify system settings"
    echo ""
    echo "Please run with sudo:"
    echo "  sudo bash scripts/increase_file_watchers.sh"
    echo ""
    echo "Or manually run these commands:"
    echo "  sudo sysctl -w fs.inotify.max_user_watches=$RECOMMENDED_LIMIT"
    echo "  echo 'fs.inotify.max_user_watches=$RECOMMENDED_LIMIT' | sudo tee -a /etc/sysctl.conf"
    exit 1
fi

# Temporarily increase limit (until reboot)
echo "Setting temporary limit..."
sysctl -w fs.inotify.max_user_watches=$RECOMMENDED_LIMIT

# Make it permanent
echo "Making change permanent..."
if grep -q "fs.inotify.max_user_watches" /etc/sysctl.conf; then
    # Update existing entry
    sed -i "s/^fs.inotify.max_user_watches=.*/fs.inotify.max_user_watches=$RECOMMENDED_LIMIT/" /etc/sysctl.conf
    echo "Updated existing entry in /etc/sysctl.conf"
else
    # Add new entry
    echo "fs.inotify.max_user_watches=$RECOMMENDED_LIMIT" >> /etc/sysctl.conf
    echo "Added new entry to /etc/sysctl.conf"
fi

# Verify
NEW_LIMIT=$(cat /proc/sys/fs/inotify/max_user_watches)
echo ""
echo "========================================="
echo "✅ File watcher limit increased successfully!"
echo "   Old limit: $CURRENT_LIMIT"
echo "   New limit: $NEW_LIMIT"
echo "========================================="
echo ""
echo "You can now restart your development servers."
