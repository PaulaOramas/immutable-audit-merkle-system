"""
Conftest global — Deshabilita autenticación para tests existentes.

Los tests de autenticación específicos la re-habilitan explícitamente.
"""

import os

# Deshabilitar autenticación y cola por defecto en tests
os.environ.setdefault("AUTH_ENABLED", "false")
os.environ.setdefault("QUEUE_ENABLED", "false")
os.environ.setdefault("SCHEDULER_ENABLED", "false")
