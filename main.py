#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ejecutar con:
    python main.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from gui import main  # noqa: E402

if __name__ == "__main__":
    main()
