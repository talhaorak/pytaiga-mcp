#!/bin/bash

# Run unit tests
source .venv/bin/activate
python -m pytest tests/test_server.py -v