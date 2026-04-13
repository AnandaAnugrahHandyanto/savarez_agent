#!/usr/bin/env python3
"""
AI Agent Runner wrapper script.
"""
import sys
import os
import fire
import logging
from agent.core import AIAgent, main

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    fire.Fire(main)
