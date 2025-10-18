#!/bin/bash

# Test the codebot CLI

# Create a temp test directory
TEST_DIR=$(mktemp -d)
echo "Created test directory: $TEST_DIR"

cd "$TEST_DIR"

# Create a simple Python project
mkdir src tests
cat > src/main.py <<EOF
def greet(name):
    return f"Hello, {name}!"

if __name__ == "__main__":
    print(greet("World"))
EOF

cat > tests/test_main.py <<EOF
from src.main import greet

def test_greet():
    assert greet("Alice") == "Hello, Alice!"
EOF

cat > README.md <<EOF
# Test Project

A simple test project.
EOF

echo "Created test project files"
echo ""
echo "Test 1: Run /init command"
echo "/init" | timeout 5 codebot || echo "Command finished"

echo ""
echo "Test 2: Run /index command"
echo "/index" | timeout 5 codebot || echo "Command finished"

echo ""
echo "Test 3: Run /read command"
echo "/read src/main.py" | timeout 5 codebot || echo "Command finished"

echo ""
echo "Test files created:"
ls -la

# Cleanup
cd -
rm -rf "$TEST_DIR"
echo "Cleaned up test directory"
