"""
Auto-DFA API

FastAPI-based REST API for the DFA Generator system.
Provides endpoints for DFA generation and health checks.

Security features:
  - Input sanitization (max length, whitespace stripping)
  - Rate limiting via slowapi (10 req/min on /generate)
  - Optional API key authentication (set API_KEY env var to enable)
"""

import re
import time
import traceback
import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Request, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, field_validator, ValidationError as PydanticValidationError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.responses import JSONResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# --- Rate Limiter ---
limiter = Limiter(key_func=get_remote_address)

# --- API Key Auth (optional) ---
API_KEY = os.environ.get("API_KEY")  # Set to enable auth; unset = disabled
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: Optional[str] = Security(api_key_header)):
    """Validate API key if API_KEY env var is set. No-op when unset."""
    if API_KEY is None:
        return  # Auth disabled
    if api_key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "Invalid or missing API key",
                "error_type": "AuthenticationError",
                "hint": "Provide a valid X-API-Key header."
            }
        )

# Import the existing system from your main.py
from main import DFAGeneratorSystem

# Import custom exceptions for proper error handling
from core.repair import LLMConnectionError


# --- Custom Exception Classes ---

class DFAValidationError(Exception):
    """Raised when DFA validation fails due to invalid specification."""
    pass


class ServiceUnavailableError(Exception):
    """Raised when a required service (Ollama, etc.) is unavailable."""
    pass


# --- Lifespan Management (Replaces Global Variable) ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle.
    Uses app.state for proper singleton management instead of global variables.
    """
    # Startup
    logger.info("Initializing DFA Generator System...")
    try:
        app.state.system = DFAGeneratorSystem()
        app.state.system_error = None
        logger.info("DFA Generator System initialized successfully!")
    except Exception as e:
        logger.error(f"Failed to initialize system: {e}")
        app.state.system = None
        app.state.system_error = str(e)
    
    yield
    
    # Shutdown
    logger.info("Shutting down DFA Generator System...")
    app.state.system = None


app = FastAPI(
    title="Auto-DFA API",
    version="1.0.0",
    description="AI-Powered DFA (Deterministic Finite Automaton) Generator",
    lifespan=lifespan
)

# Register rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# --- CORS Configuration ---
# Get allowed origins from environment variable or use defaults
ALLOWED_ORIGINS = os.environ.get(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:3000"
).split(",")

# In development, you might want to allow all origins
if os.environ.get("ENVIRONMENT") == "development":
    ALLOWED_ORIGINS = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Input Sanitization Constants ---
MAX_PROMPT_LENGTH = 500
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


# --- Request/Response Models ---

class QueryRequest(BaseModel):
    prompt: str

    @field_validator("prompt", mode="before")
    @classmethod
    def sanitize_prompt(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("Prompt must be a string.")
        v = v.strip()
        if not v:
            raise ValueError("Prompt cannot be empty.")
        if len(v) > MAX_PROMPT_LENGTH:
            raise ValueError(f"Prompt exceeds maximum length of {MAX_PROMPT_LENGTH} characters.")
        # Strip control characters
        v = _CONTROL_CHAR_RE.sub("", v)
        return v


class ErrorDetail(BaseModel):
    error: str
    error_type: str
    hint: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    system_initialized: bool
    message: str
    version: str = "1.0.0"


# --- Helper Functions ---

def get_system(request: Request) -> DFAGeneratorSystem:
    """
    Dependency function to get the system instance from app.state.
    Raises appropriate HTTP exceptions if system is not available.
    """
    if not hasattr(request.app.state, 'system') or request.app.state.system is None:
        error_msg = getattr(request.app.state, 'system_error', 'Unknown initialization error')
        raise HTTPException(
            status_code=503,
            detail={
                "error": "System not initialized",
                "error_type": "ServiceUnavailable",
                "hint": f"Check that Ollama is running. Init error: {error_msg}"
            }
        )
    return request.app.state.system


# --- API Endpoints ---

@app.get("/health", response_model=HealthResponse)
@limiter.limit("60/minute")
async def health_check(request: Request):
    """Health check endpoint to verify API is running."""
    system_initialized = (
        hasattr(request.app.state, 'system') and 
        request.app.state.system is not None
    )
    
    return HealthResponse(
        status="healthy" if system_initialized else "degraded",
        system_initialized=system_initialized,
        message="Auto-DFA API is running" if system_initialized else "System not fully initialized"
    )


@app.post("/generate", dependencies=[Depends(verify_api_key)])
@limiter.limit("10/minute")
async def generate_dfa(request: Request, query: QueryRequest):
    """
    Generate a DFA from a natural language description.
    
    Returns:
        - 200: DFA generated successfully
        - 400: Bad request (invalid prompt format)
        - 401: Unauthorized (invalid API key)
        - 429: Too many requests
        - 503: Service unavailable (Ollama not running)
        - 500: Internal server error
    """
    request_id = str(uuid.uuid4())[:8]
    t_start = time.time()
    logger.info(f"[API][{request_id}] Received request: '{query.prompt}'")
    
    # Get system instance (raises 503 if not available)
    system = get_system(request)
    
    try:
        timings = {}

        # 1. Analyze user prompt into a LogicSpec
        logger.info(f"[API][{request_id}] Step 1: Analyzing prompt...")
        t_phase = time.time()
        try:
            spec = system.analyst.analyze(query.prompt)
        except ValueError as e:
            # Invalid prompt format
            raise HTTPException(
                status_code=400,
                detail={
                    "error": str(e),
                    "error_type": "ValidationError",
                    "hint": "Check your prompt format. Use patterns like: 'ends with a', 'contains 01', 'divisible by 3'"
                }
            )
        timings["analysis_ms"] = round((time.time() - t_phase) * 1000, 1)
        
        logger.info(f"[API][{request_id}] Analysis complete: {spec.logic_type} -> {spec.target}")
        
        # 2. Architect the DFA structure
        logger.info(f"[API][{request_id}] Step 2: Designing DFA...")
        t_phase = time.time()
        try:
            dfa_obj = system.architect.design(spec)
        except LLMConnectionError as e:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": str(e),
                    "error_type": "ServiceUnavailable",
                    "hint": "Ensure Ollama is running with 'ollama serve'"
                }
            )
        except ValueError as e:
            # Usually means specification too complex
            raise HTTPException(
                status_code=400,
                detail={
                    "error": str(e),
                    "error_type": "ValidationError",
                    "hint": "Try simplifying your request. Complex compound conditions may exceed resource limits."
                }
            )
        timings["architecture_ms"] = round((time.time() - t_phase) * 1000, 1)
        
        logger.info(f"[API][{request_id}] DFA designed with {len(dfa_obj.states)} states")
        
        # 3. Validate against deterministic ground truth
        logger.info(f"[API][{request_id}] Step 3: Validating DFA...")
        t_phase = time.time()
        is_valid, error_msg = system.validator.validate(dfa_obj, spec)
        timings["validation_ms"] = round((time.time() - t_phase) * 1000, 1)
        
        total_ms = round((time.time() - t_start) * 1000, 1)
        logger.info(f"[API][{request_id}] Done in {total_ms}ms — valid={is_valid}")
        
        return {
            "valid": is_valid,
            "message": error_msg if not is_valid else "DFA generated successfully",
            "dfa": dfa_obj.model_dump(),
            "spec": spec.model_dump(),
            "performance": {
                "total_ms": total_ms,
                **timings
            }
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
        
    except LLMConnectionError as e:
        # LLM/Ollama service errors
        logger.error(f"[API] Ollama connection error: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail={
                "error": str(e),
                "error_type": "ServiceUnavailable",
                "hint": "The AI service (Ollama) is not reachable. Start it with 'ollama serve'."
            }
        )
        
    except PydanticValidationError as e:
        # Pydantic validation errors (bad input format)
        logger.error(f"[API] Validation error: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid request format",
                "error_type": "ValidationError",
                "hint": "Ensure your request body contains a valid 'prompt' field."
            }
        )
        
    except ConnectionError as e:
        # Network/connection errors
        logger.error(f"[API] Connection error: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Failed to connect to required services",
                "error_type": "ConnectionError",
                "hint": "Check that all required services (Ollama) are running and accessible."
            }
        )
        
    except Exception as e:
        # Unexpected errors - log full traceback
        logger.error(f"[API] Unexpected error: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Internal server error: {str(e)}",
                "error_type": "RuntimeError",
                "hint": "An unexpected error occurred. Check server logs for details."
            }
        )


# --- Export Endpoints ---

@app.post("/export/json", dependencies=[Depends(verify_api_key)])
@limiter.limit("30/minute")
async def export_json(request: Request, query: QueryRequest):
    """
    Generate and return DFA as downloadable JSON.
    Same as /generate but returns a file attachment.
    """
    system = get_system(request)
    try:
        spec = system.analyst.analyze(query.prompt)
        dfa_obj = system.architect.design(spec)
        is_valid, error_msg = system.validator.validate(dfa_obj, spec)

        import json
        from starlette.responses import Response

        content = json.dumps({
            "valid": is_valid,
            "dfa": dfa_obj.model_dump(),
            "spec": spec.model_dump()
        }, indent=2)

        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=dfa_export.json"}
        )
    except LLMConnectionError as e:
        raise HTTPException(status_code=503, detail={"error": str(e), "error_type": "ServiceUnavailable"})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e), "error_type": "RuntimeError"})


@app.post("/export/dot", dependencies=[Depends(verify_api_key)])
@limiter.limit("30/minute")
async def export_dot(request: Request, query: QueryRequest):
    """
    Generate DFA and return as Graphviz DOT format.
    """
    system = get_system(request)
    try:
        spec = system.analyst.analyze(query.prompt)
        dfa_obj = system.architect.design(spec)

        # Build DOT string
        dfa_data = dfa_obj.model_dump()
        lines = ["digraph DFA {", "  rankdir=LR;", "  node [shape=circle];"]

        # Accept states get double circle
        for state in dfa_data.get("accept_states", []):
            lines.append(f'  "{state}" [shape=doublecircle];')

        # Start arrow
        start = dfa_data.get("start_state", "q0")
        lines.append(f'  __start__ [shape=point];')
        lines.append(f'  __start__ -> "{start}";')

        # Transitions
        for src, trans in dfa_data.get("transitions", {}).items():
            # Group by destination
            dest_symbols = {}
            for symbol, dest in trans.items():
                dest_symbols.setdefault(dest, []).append(symbol)
            for dest, symbols in dest_symbols.items():
                label = ",".join(symbols)
                lines.append(f'  "{src}" -> "{dest}" [label="{label}"];')

        lines.append("}")
        dot_content = "\n".join(lines)

        from starlette.responses import Response
        return Response(
            content=dot_content,
            media_type="text/vnd.graphviz",
            headers={"Content-Disposition": "attachment; filename=dfa_export.dot"}
        )
    except LLMConnectionError as e:
        raise HTTPException(status_code=503, detail={"error": str(e), "error_type": "ServiceUnavailable"})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e), "error_type": "RuntimeError"})


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Auto-DFA API",
        "version": "1.0.0",
        "description": "AI-Powered DFA Generator",
        "endpoints": {
            "/health": "Health check (GET)",
            "/generate": "Generate DFA from prompt (POST)",
            "/export/json": "Export DFA as JSON file (POST)",
            "/export/dot": "Export DFA as Graphviz DOT file (POST)"
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", "8000"))
    
    uvicorn.run(app, host=host, port=port)