#!/bin/bash

# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Download spaCy model
python -m spacy download en_core_web_sm

# Run migrations (if needed)
python -m alembic upgrade head

# Start server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
