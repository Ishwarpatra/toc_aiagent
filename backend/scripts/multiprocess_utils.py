def process_test_chunk_serialized(chunk_data: tuple) -> List[Dict]:
    """
    Process a chunk of tests in a separate process.
    This function is designed to be serializable for multiprocessing.
    """
    chunk, chunk_idx, model_name, max_product_states = chunk_data
    
    # Create a fresh system for this process
    from main import DFAGeneratorSystem
    system = DFAGeneratorSystem(model_name=model_name, max_product_states=max_product_states)
    
    results = []
    for idx, case in enumerate(chunk):
        # Process the test case
        start_time = time.time()
        
        try:
            # Analyze the prompt
            logic_spec = system.analyst.analyze(case["prompt"])
            
            # Build the DFA
            dfa = system.architect.design(logic_spec)
            
            # Validate against oracle strings if provided
            oracle_validated = True
            error_msg = ""
            
            # Check acceptance strings
            if case.get("must_accept"):
                accept_strings = case["must_accept"].split(";")
                for test_str in accept_strings:
                    if test_str.strip() and not dfa.accepts(test_str.strip()):
                        oracle_validated = False
                        error_msg = f"Failed to accept: {test_str.strip()}"
                        break
            
            # Check rejection strings if acceptance passed
            if oracle_validated and case.get("must_reject"):
                reject_strings = case["must_reject"].split(";")
                for test_str in reject_strings:
                    if test_str.strip() and dfa.accepts(test_str.strip()):
                        oracle_validated = False
                        error_msg = f"Wrongly accepted: {test_str.strip()}"
                        break
            
            # Determine status
            if oracle_validated:
                status = "PASS"
            else:
                status = "ORACLE_FAIL"
            
            # Record result
            result = {
                "status": status,
                "time_ms": round((time.time() - start_time) * 1000, 2),
                "states": len(dfa.states),
                "oracle_validated": oracle_validated,
                "error": error_msg,
                "prompt": case["prompt"],
                "category": case.get("category", "Unknown"),
                "expected_type": case.get("expected_type", ""),
                "difficulty": case.get("difficulty", "unknown")
            }
            
        except Exception as e:
            result = {
                "status": "ERROR",
                "time_ms": round((time.time() - start_time) * 1000, 2),
                "states": 0,
                "oracle_validated": False,
                "error": str(e),
                "prompt": case["prompt"],
                "category": case.get("category", "Unknown"),
                "expected_type": case.get("expected_type", ""),
                "difficulty": case.get("difficulty", "unknown")
            }
        
        results.append(result)
    
    return results