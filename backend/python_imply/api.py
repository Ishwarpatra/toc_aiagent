# backend/python_imply/api.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any

# Import the existing system from your main.py
from main import DFAGeneratorSystem

app = FastAPI(title="Auto-DFA API")

# Enable CORS so the React frontend (port 5173) can talk to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    prompt: str

# Initialize the modular AI system once
system = DFAGeneratorSystem()

@app.post("/generate")
async def generate_dfa(request: QueryRequest):
    try:
        # 1. Analyze user prompt into a LogicSpec
        spec = system.analyst.analyze(request.prompt)
        
        # 2. Architect the DFA structure recursively
        dfa_obj = system.architect.design(spec)
        
        # 3. Validate against deterministic ground truth
        is_valid, error_msg = system.validator.validate(dfa_obj, spec)
        
        return {
            "valid": is_valid,
            "message": error_msg if not is_valid else "DFA generated successfully",
            "dfa": dfa_obj.model_dump(), # Serialize to JSON
            "spec": spec.model_dump()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)