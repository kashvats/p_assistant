#!/usr/bin/env python3
"""Source-archive entry point for the versioned Living Assistant installer."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from living_assistant.release_manager import main
raise SystemExit(main())
