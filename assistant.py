#!/usr/bin/env python3
"""
Personal Assistant & Life Coach

A file-based personal development assistant with AI-powered suggestions.
"""

import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

from cli import main

if __name__ == '__main__':
    sys.exit(main())