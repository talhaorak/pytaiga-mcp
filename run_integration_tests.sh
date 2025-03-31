#!/bin/bash

# Run integration tests
source .venv/bin/activate
python -m pytest tests/test_integration.py -v -m integration
