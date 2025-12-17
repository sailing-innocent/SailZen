# Script to install better-sqlite3 with C++20 support for Node.js v24
# Set environment variable to use C++20
$env:CXXFLAGS = "/std:c++20"
$env:CPPFLAGS = "/std:c++20"

# Install better-sqlite3
pnpm add better-sqlite3


