"""Vercel Serverless Entrypoint for Pixora FastAPI Application."""
from gateway import app

# Expose ASGI application
app = app
