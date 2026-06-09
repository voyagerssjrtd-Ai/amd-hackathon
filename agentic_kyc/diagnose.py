#!/usr/bin/env python3
"""
Streamlit Session Initialization Diagnostic
Helps diagnose SessionInfo initialization issues
"""

import os
import sys
from pathlib import Path

print("=" * 60)
print("STREAMLIT DIAGNOSTICS")
print("=" * 60)

# Check Python version
print(f"\n✓ Python Version: {sys.version.split()[0]}")

# Check if Streamlit is installed
try:
    import streamlit as st
    print(f"✓ Streamlit: {st.__version__}")
except ImportError:
    print("✗ Streamlit not installed")
    sys.exit(1)

# Check environment
print(f"\n✓ Current Directory: {os.getcwd()}")
print(f"✓ User: {os.getenv('USERNAME', 'Unknown')}")

# Check key files
project_files = [
    "app.py",
    "requirements.txt",
    ".env",
    "agents/compliance_agent.py",
    "services/llm_service.py",
]

print(f"\n✓ Project Files:")
for file in project_files:
    exists = "✓" if Path(file).exists() else "✗"
    print(f"  {exists} {file}")

# Check environment configuration
print(f"\n✓ Configuration:")
print(f"  - BASE_URL: {os.getenv('BASE_URL', 'Not set')}")
print(f"  - MODEL_NAME: {os.getenv('MODEL_NAME', 'Not set')}")
print(f"  - DATABASE_PATH: {os.getenv('DATABASE_PATH', 'Not set')}")

# Suggest fixes
print(f"\n" + "=" * 60)
print("RECOMMENDED ACTIONS:")
print("=" * 60)

fixes = [
    ("1", "Clear Streamlit cache", "streamlit cache clear"),
    ("2", "Restart Streamlit server", "streamlit run app.py --server.address 0.0.0.0 --server.port 8501"),
    ("3", "Check vLLM is running", "curl http://127.0.0.1:8000/v1/models"),
    ("4", "Check Streamlit responds", "curl http://127.0.0.1:8501"),
]

for num, desc, cmd in fixes:
    print(f"\n{num}. {desc}")
    print(f"   $ {cmd}")

print(f"\n" + "=" * 60)
print("For detailed troubleshooting, see: UPLOAD_TROUBLESHOOTING.md")
print("=" * 60)
