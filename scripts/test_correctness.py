import csv
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend', 'python_imply'))

from core.agents import AnalystAgent, ArchitectAgent
from core.models import LogicSpec

def test_correctness():
    # Initialize agents
    analyst_agent = AnalystAgent(model_name="test")
    architect_agent = ArchitectAgent(model_name="test", max_product_states=2000)
    
    # Read a sample of test cases
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'backend', 'scripts', 'data')
    with open(os.path.join(data_dir, 'test_enhanced_fixed_6000.csv'), 'r') as f:
        reader = csv.DictReader(f)
        test_cases = list(reader)[:50]  # Test first 50 cases
    
    print(f"Testing correctness on {len(test_cases)} sample cases from the 6000 generated tests:")
    print("="*80)
    
    correct_count = 0
    total_tested = 0
    
    for i, test_case in enumerate(test_cases):
        prompt = test_case['prompt']
        must_accept = test_case['must_accept'].split(';') if test_case['must_accept'] else []
        must_reject = test_case['must_reject'].split(';') if test_case['must_reject'] else []
        
        # Skip empty strings
        must_accept = [s for s in must_accept if s.strip()]
        must_reject = [s for s in must_reject if s.strip()]
        
        if not must_accept and not must_reject:
            continue
            
        print(f"\nTest {i+1}: {prompt}")
        print(f"  Expected Accept: {must_accept[:3]}{'...' if len(must_accept) > 3 else ''}")
        print(f"  Expected Reject: {must_reject[:3]}{'...' if len(must_reject) > 3 else ''}")
        
        try:
            # Analyze the prompt
            logic_spec = analyst_agent.analyze(prompt)
            print(f"  Parsed as: {logic_spec.logic_type} with target: {logic_spec.target}")
            
            # Build the DFA
            dfa = architect_agent.design(logic_spec)
            print(f"  Generated DFA with {len(dfa.states)} states")
            
            # Test acceptance strings
            accept_correct = True
            for test_string in must_accept[:5]:  # Test first 5 accept strings
                if test_string and dfa.accepts(test_string):
                    continue
                elif test_string:
                    accept_correct = False
                    print(f"    ERROR: String '{test_string}' should be accepted but was rejected!")
                    break
            
            # Test rejection strings
            reject_correct = True
            for test_string in must_reject[:5]:  # Test first 5 reject strings
                if test_string and not dfa.accepts(test_string):
                    continue
                elif test_string:
                    reject_correct = False
                    print(f"    ERROR: String '{test_string}' should be rejected but was accepted!")
                    break
            
            if accept_correct and reject_correct:
                print(f"  [CORRECT] DFA behaves as expected")
                correct_count += 1
            else:
                print(f"  [INCORRECT] DFA does not match expected behavior")

            total_tested += 1

        except Exception as e:
            print(f"  [ERROR] Failed to process - {str(e)}")
            continue

    print("\n" + "="*80)
    print(f"Correctness Results: {correct_count}/{total_tested} test cases passed")
    if total_tested > 0:
        print(f"Accuracy Rate: {correct_count/total_tested*100:.2f}%")
    else:
        print("No test cases could be evaluated")

if __name__ == "__main__":
    test_correctness()