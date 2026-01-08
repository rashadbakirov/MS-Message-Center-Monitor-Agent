#!/bin/bash

# Git History Reset Script
# This script will reset the commit history to a single "Initial commit"

set -e  # Exit on error

echo "=============================================================================="
echo "  Git History Reset Script"
echo "=============================================================================="
echo ""
echo "⚠️  WARNING: This will PERMANENTLY DELETE all commit history!"
echo "⚠️  This operation CANNOT be undone!"
echo ""
echo "This script will:"
echo "  1. Create an orphan branch with no commit history"
echo "  2. Add all current files to a single 'Initial commit'"
echo "  3. Force-push to replace the main branch on GitHub"
echo ""
echo "Press Ctrl+C now to cancel, or press Enter to continue..."
read -r

echo ""
echo "Step 1: Creating orphan branch..."
git checkout --orphan new-clean-history

echo "Step 2: Staging all files..."
git add -A

echo "Step 3: Creating Initial commit..."
git commit -m "Initial commit"

echo "Step 4: Renaming to main branch..."
git branch -M new-clean-history main

echo ""
echo "Current state:"
git log --oneline -1

echo ""
echo "⚠️  FINAL WARNING: About to force-push to GitHub!"
echo "This will permanently delete all existing commit history."
echo ""
echo "Press Ctrl+C now to cancel, or press Enter to execute the force-push..."
read -r

echo ""
echo "Step 5: Force-pushing to GitHub..."
git push -f origin main

echo ""
echo "=============================================================================="
echo "✅ SUCCESS! Commit history has been reset."
echo "=============================================================================="
echo ""
echo "Verification:"
git log --oneline
echo ""
echo "Your repository now has only 1 commit in the history."
echo "All files have been preserved."
echo ""
