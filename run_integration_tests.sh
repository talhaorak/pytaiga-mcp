#!/bin/bash

# Run integration tests
uv run pytest tests/test_integration.py -v -m integration
