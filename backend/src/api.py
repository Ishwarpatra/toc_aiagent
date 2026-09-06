"""
Auto-DFA API

FastAPI-based REST API for the DFA Generator system.
Provides endpoints for DFA generation and health checks.

Security features:
  - Input sanitization (max length, whitespace stripping)
  - Rate limiting via slowapi (10 req/min on /generate)
  - Optional API key authentication (set API_KEY env var to enable)
"""

import json
import re
import base64
import time
import traceback
import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import Optional, Dict, List, Any

from fastapi import FastAPI, HTTPException, Request, Depends, Security, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, field_validator, ValidationError as PydanticValidationError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.responses import JSONResponse, Response

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

# Import custom exceptions and reverse engineering components
from core.repair import LLMConnectionError
from core import GrammarBuilder, VisionAgent, DescriberAgent


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
    
    # Shutdown — call close() first to flush diskcache WAL before nulling reference
    logger.info("Shutting down DFA Generator System...")
    if app.state.system is not None:
        try:
            app.state.system.close()
        except Exception as exc:
            logger.warning(f"Error during system shutdown: {exc}")
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

# In development, allow all origins but WITHOUT credentials
# (CORS spec forbids allow_credentials=True with wildcard origin)
IS_DEV = os.environ.get("ENVIRONMENT") == "development"
if IS_DEV:
    ALLOWED_ORIGINS = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=not IS_DEV,  # Credentials incompatible with wildcard
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Input Sanitization Constants ---
MAX_PROMPT_LENGTH = 500
# Regex patterns for prompt injection hardening
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# LLM role-override tokens common in Ollama/Llama/Qwen/Mistral model formats
_INJECTION_TOKEN_RE = re.compile(
    r"<\|im_start\|>|<\|im_end\|>|\[INST\]|\[/INST\]|<s>|</s>"
    r"|<<SYS>>|<</SYS>>|\[SYSTEM\]|\[USER\]|\[ASSISTANT\]",
    re.IGNORECASE
)


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
        # Strip C0 control characters
        v = _CONTROL_CHAR_RE.sub("", v)
        # Collapse injection-style blank-line padding (>2 consecutive newlines -> 2)
        v = re.sub(r"\n{3,}", "\n\n", v)
        # Strip LLM role-override tokens that could hijack the system prompt
        v = _INJECTION_TOKEN_RE.sub("", v).strip()
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


class ReverseEngineerResponse(BaseModel):
    success: bool
    dfa: Optional[Dict[str, Any]] = None
    grammar: Optional[Dict[str, List[str]]] = None
    grammar_formatted: Optional[str] = None
    description: Optional[str] = None
    valid: bool = False
    error: Optional[str] = None


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
        # Unexpected errors - log full traceback but don't expose internals to client
        logger.error(f"[API] Unexpected error: {str(e)}")
        logger.error(traceback.format_exc())
        # In production, hide raw exception detail to avoid information leakage
        client_msg = str(e) if IS_DEV else "An unexpected error occurred."
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Internal server error: {client_msg}",
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
        client_msg = str(e) if IS_DEV else "Export failed."
        raise HTTPException(status_code=500, detail={"error": client_msg, "error_type": "RuntimeError"})


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

        return Response(
            content=dot_content,
            media_type="text/vnd.graphviz",
            headers={"Content-Disposition": "attachment; filename=dfa_export.dot"}
        )
    except LLMConnectionError as e:
        raise HTTPException(status_code=503, detail={"error": str(e), "error_type": "ServiceUnavailable"})
    except Exception as e:
        client_msg = str(e) if IS_DEV else "Export failed."
        raise HTTPException(status_code=500, detail={"error": client_msg, "error_type": "RuntimeError"})


ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


@app.post("/reverse-engineer", response_model=ReverseEngineerResponse, dependencies=[Depends(verify_api_key)])
@limiter.limit("10/minute")
async def reverse_engineer_dfa(request: Request, file: UploadFile = File(...)):
    """
    Reverse Engineer a DFA from an uploaded state diagram image.

    3-Phase Neuro-Symbolic Pipeline:
    1. Perception (AI): VisionAgent parses image -> strict DFA model + DeterministicValidator.
    2. Formalization (Deterministic Math): GrammarBuilder computes Right-Linear Regular Grammar.
    3. Translation (AI): DescriberAgent translates DFA + Grammar into a natural language sentence.
    """
    if not file:
        raise HTTPException(
            status_code=400,
            detail={"error": "No file uploaded", "error_type": "ValidationError"}
        )

    # Validate Content-Type
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail={
                "error": f"Unsupported image type: '{content_type}'. Allowed types: PNG, JPEG, WEBP.",
                "error_type": "InvalidFileType"
            }
        )

    try:
        # Read file bytes into memory
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(
                status_code=400,
                detail={"error": "Uploaded image file is empty.", "error_type": "EmptyFile"}
            )
        if len(file_bytes) > MAX_IMAGE_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail={"error": "Image file exceeds maximum allowed size of 10MB.", "error_type": "PayloadTooLarge"}
            )

        # Convert to base64
        base64_img = base64.b64encode(file_bytes).decode("utf-8")

        # Step 1: VisionAgent perception
        vision_agent = VisionAgent()
        dfa_obj = vision_agent.process_image(base64_img)

        # Step 2: GrammarBuilder mathematical formalization
        grammar = GrammarBuilder.build_from_dfa(dfa_obj)
        grammar_formatted = GrammarBuilder.format_grammar(grammar)

        # Step 3: DescriberAgent translation
        describer_agent = DescriberAgent()
        description = describer_agent.describe(dfa_obj, grammar)

        return ReverseEngineerResponse(
            success=True,
            dfa=dfa_obj.model_dump(),
            grammar=grammar,
            grammar_formatted=grammar_formatted,
            description=description,
            valid=True
        )

    except HTTPException:
        raise
    except ValueError as ve:
        logger.warning(f"[API] Reverse engineering validation failed: {ve}")
        raise HTTPException(
            status_code=422,
            detail={"error": str(ve), "error_type": "DFAValidationError"}
        )
    except Exception as e:
        logger.error(f"[API] Reverse engineering failed: {e}")
        logger.error(traceback.format_exc())
        client_msg = str(e) if IS_DEV else "Failed to reverse engineer DFA diagram."
        raise HTTPException(
            status_code=500,
            detail={"error": client_msg, "error_type": "RuntimeError"}
        )


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
            "/reverse-engineer": "Reverse engineer DFA from image diagram (POST)",
            "/export/json": "Export DFA as JSON file (POST)",
            "/export/dot": "Export DFA as Graphviz DOT file (POST)",
            "/oracle/verify": "Oracle truth verification (POST)"
        }
    }


# ---------------------------------------------------------------------------
# Oracle endpoint — wraps core/oracle.py for production runtime monitoring
# ---------------------------------------------------------------------------

class OracleRequest(BaseModel):
    """Request model for oracle verification."""
    op_type: str
    pattern: str
    alphabet: list[str] = ["0", "1"]
    test_strings: list[str] = []

    @field_validator("op_type")
    @classmethod
    def validate_op_type(cls, v: str) -> str:
        allowed = {
            "STARTS_WITH", "NOT_STARTS_WITH", "ENDS_WITH", "NOT_ENDS_WITH",
            "CONTAINS", "NOT_CONTAINS", "EXACT_LENGTH", "DIVISIBLE_BY",
            "EVEN_COUNT", "ODD_COUNT", "NO_CONSECUTIVE",
        }
        if v.upper() not in allowed:
            raise ValueError(f"Invalid op_type: {v}. Allowed: {sorted(allowed)}")
        return v.upper()


@app.post("/oracle/verify")
@limiter.limit("30/minute")
async def oracle_verify(request: Request, body: OracleRequest):
    """
    Oracle truth verification endpoint.

    Verifies test strings against a given condition using the canonical Oracle,
    and optionally generates authoritative accept/reject examples.

    Use this for production runtime monitoring and DFA correctness assertions.
    """
    from core.oracle import check_condition, get_oracle_strings

    # Classify provided test strings
    results = []
    for s in body.test_strings:
        satisfies = check_condition(s, body.op_type, body.pattern, body.alphabet)
        results.append({"string": s, "satisfies": satisfies})

    # Generate authoritative oracle strings
    accept_examples, reject_examples = get_oracle_strings(
        body.op_type, body.pattern, body.alphabet
    )

    return {
        "op_type": body.op_type,
        "pattern": body.pattern,
        "alphabet": body.alphabet,
        "test_results": results,
        "oracle_accept_examples": accept_examples,
        "oracle_reject_examples": reject_examples,
    }


if __name__ == "__main__":
    import uvicorn
    
    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", "8000"))
    
    uvicorn.run(app, host=host, port=port)