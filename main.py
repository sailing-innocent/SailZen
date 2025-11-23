# -*- coding: utf-8 -*-
# @file main.py
# @brief FastAPI application entry point
# @author sailing-innocent
# @date 2025-04-21

import os
import sys
from pathlib import Path

# Load environment variables FIRST, before any other imports
from dotenv import load_dotenv
import argparse

# Parse arguments to determine which env file to load
parser = argparse.ArgumentParser()
parser.add_argument("--mode", type=str, default="dev", help="Mode: dev, debug, prod")
args, unknown = parser.parse_known_args()

# Determine env file based on mode
if args.mode == "dev":
    env_file = ".env.dev"
elif args.mode == "debug":
    env_file = ".env.debug"
elif args.mode == "prod":
    env_file = ".env.prod"
else:
    env_file = ".env"

# Load environment variables before importing any server modules
env_path = Path(__file__).parent / env_file
if env_path.exists():
    print(f"Loading environment variables from {env_file}")
    load_dotenv(env_path, encoding="utf-8")
else:
    # Try default .env file
    default_env = Path(__file__).parent / ".env"
    if default_env.exists():
        print(f"Loading environment variables from .env (default)")
        load_dotenv(default_env, encoding="utf-8")
    else:
        print(f"Warning: No environment file found ({env_file} or .env)")
        print("Please create .env file with POSTGRE_URI configuration")

# Verify POSTGRE_URI is set
postgre_uri = os.environ.get("POSTGRE_URI")
if not postgre_uri:
    print("ERROR: POSTGRE_URI environment variable is not set!")
    print("Please set it in your .env file:")
    print("  POSTGRE_URI=postgresql://username:password@localhost:5432/sailzen")
    sys.exit(1)

# Validate URI encoding
try:
    # Test if the URI can be properly encoded/decoded
    test_encode = postgre_uri.encode("utf-8").decode("utf-8")
    print(f"✓ Database URI encoding validated")
except UnicodeError as e:
    print(f"ERROR: Database URI contains invalid characters!")
    print(f"Error: {e}")
    print("")
    print("Common issues:")
    print("  1. Password contains non-ASCII characters (中文密码)")
    print("  2. .env file is not saved in UTF-8 encoding")
    print("  3. Special characters not properly escaped")
    print("")
    print("Solutions:")
    print("  1. Use only ASCII characters (a-z, A-Z, 0-9) in password")
    print(
        "  2. Save .env file as UTF-8 encoding (in Notepad: Save As -> Encoding: UTF-8)"
    )
    print("  3. URL-encode special characters in password")
    print("")
    print("Example: If password is 'pass@word#123'")
    print("  Use: postgresql://user:pass%40word%23123@localhost:5432/sailzen")
    sys.exit(1)

# NOW import server modules (after env vars are loaded)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from server.router import (
    works_router,
    nodes_router,
    entities_router,
    relations_router,
    extract_router,
    sessions_router,
    changesets_router,
    reviews_router,
    events_router,
    collections_router,
    brainstorm_router,
)
from server.service.llm_service import init_llm_service


# Create FastAPI app
app = FastAPI(
    title="SailZen API",
    description="Backend API for LLM-driven worldview construction system",
    version="0.1.0",
)

# Initialize LLM service
llm_api_key = os.environ.get("LLM_API_KEY", "")
llm_endpoint = os.environ.get("LLM_ENDPOINT", "https://api.deepseek.com/v1")
llm_model = os.environ.get("LLM_MODEL", "deepseek-chat")
llm_temperature = float(os.environ.get("LLM_TEMPERATURE", "0.3"))

if llm_api_key:
    print(f"✓ Initializing LLM service: {llm_model} at {llm_endpoint}")
    init_llm_service(
        api_key=llm_api_key,
        endpoint=llm_endpoint,
        model=llm_model,
        temperature=llm_temperature,
    )
else:
    print("⚠ Warning: LLM_API_KEY not set. LLM features will not be available.")
    print("  Set LLM_API_KEY in your .env file to enable real LLM integration.")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(works_router)
app.include_router(nodes_router)
app.include_router(entities_router)
app.include_router(relations_router)
app.include_router(extract_router)
app.include_router(sessions_router)
app.include_router(changesets_router)
app.include_router(reviews_router)
app.include_router(events_router)
app.include_router(collections_router)
app.include_router(brainstorm_router)


@app.get("/")
def root():
    """Root endpoint"""
    return {
        "message": "Welcome to SailZen API",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    print(f"Starting SailZen API in {args.mode} mode...")
    print(f"Database URI: {os.environ.get('POSTGRE_URI', 'NOT SET')[:50]}...")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
