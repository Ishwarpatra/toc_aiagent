"""
Auto-DFA API

FastAPI-based REST API for the DFA Generator system.
Provides endpoints for DFA generation and health checks.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ValidationError as PydanticValidationError
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
import traceback
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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


# --- Request/Response Models ---

class QueryRequest(BaseModel):
    prompt: str


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


@app.post("/generate")
async def generate_dfa(request: Request, query: QueryRequest):
    """
    Generate a DFA from a natural language description.
    
    Returns:
        - 200: DFA generated successfully
        - 400: Bad request (invalid prompt format)
        - 503: Service unavailable (Ollama not running)
        - 500: Internal server error
    """
    logger.info(f"[API] Received request: '{query.prompt}'")
    
    # Get system instance (raises 503 if not available)
    system = get_system(request)
    
    try:
        # 1. Analyze user prompt into a LogicSpec
        logger.info("[API] Step 1: Analyzing prompt...")
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
        
        logger.info(f"[API] Analysis complete: {spec.logic_type} -> {spec.target}")
        
        # 2. Architect the DFA structure
        logger.info("[API] Step 2: Designing DFA...")
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
        
        logger.info(f"[API] DFA designed with {len(dfa_obj.states)} states")
        
        # 3. Validate against deterministic ground truth
        logger.info("[API] Step 3: Validating DFA...")
        is_valid, error_msg = system.validator.validate(dfa_obj, spec)
        logger.info(f"[API] Validation result: valid={is_valid}")
        
        return {
            "valid": is_valid,
            "message": error_msg if not is_valid else "DFA generated successfully",
            "dfa": dfa_obj.model_dump(),
            "spec": spec.model_dump()
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


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Auto-DFA API",
        "version": "1.0.0",
        "description": "AI-Powered DFA Generator",
        "endpoints": {
            "/health": "Health check",
            "/generate": "Generate DFA from prompt (POST)"
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", "8000"))
    
    uvicorn.run(app, host=host, port=port)