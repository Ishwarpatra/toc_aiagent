# backend/python_imply/api.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
import traceback
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import the existing system from your main.py
from main import DFAGeneratorSystem

# Initialize the modular AI system
system = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global system
    logger.info("Initializing DFA Generator System...")
    try:
        system = DFAGeneratorSystem()
        logger.info("DFA Generator System initialized successfully!")
    except Exception as e:
        logger.error(f"Failed to initialize system: {e}")
    yield
    # Shutdown
    logger.info("Shutting down DFA Generator System...")

app = FastAPI(title="Auto-DFA API", version="1.0.0", lifespan=lifespan)

# Enable CORS so the React frontend (port 5173) can talk to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    prompt: str

@app.get("/health")
async def health_check():
    """Health check endpoint to verify API is running"""
    return {
        "status": "healthy",
        "system_initialized": system is not None,
        "message": "Auto-DFA API is running"
    }

@app.post("/generate")
async def generate_dfa(request: QueryRequest):
    logger.info(f"[API] Received request: '{request.prompt}'")
    
    if system is None:
        raise HTTPException(status_code=503, detail="System not initialized. Check Ollama is running.")
    
    try:
        # 1. Analyze user prompt into a LogicSpec
        logger.info("[API] Step 1: Analyzing prompt...")
        spec = system.analyst.analyze(request.prompt)
        logger.info(f"[API] Analysis complete: {spec.logic_type} -> {spec.target}")
        
        # 2. Architect the DFA structure recursively
        logger.info("[API] Step 2: Designing DFA...")
        dfa_obj = system.architect.design(spec)
        logger.info(f"[API] DFA designed with {len(dfa_obj.states)} states")
        
        # 3. Validate against deterministic ground truth
        logger.info("[API] Step 3: Validating DFA...")
        is_valid, error_msg = system.validator.validate(dfa_obj, spec)
        logger.info(f"[API] Validation result: valid={is_valid}")
        
        return {
            "valid": is_valid,
            "message": error_msg if not is_valid else "DFA generated successfully",
            "dfa": dfa_obj.model_dump(), # Serialize to JSON
            "spec": spec.model_dump()
        }
    except Exception as e:
        logger.error(f"[API] Error: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500, 
            detail={
                "error": str(e),
                "hint": "Try using quoted targets like `ends with 'a'` or `contains '01'`"
            }
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)