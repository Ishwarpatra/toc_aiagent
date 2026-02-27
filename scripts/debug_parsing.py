import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend', 'python_imply'))

from core.models import LogicSpec

# Test the specific case that's failing
prompt = "not prefixed by '00a0'"
print(f'Testing: {prompt}')
spec = LogicSpec.from_prompt(prompt)
if spec:
    print(f'Parsed as: {spec.logic_type}, target: {spec.target}')
else:
    print('No match found')

# Test other similar cases
test_cases = [
    "not prefixed by '00a0'",
    "does not start with 'ab'",
    "strings starting with 'ab'",
    "strings that end with '01'",
    "strings not ending with '01'"
]

for test_prompt in test_cases:
    spec = LogicSpec.from_prompt(test_prompt)
    if spec:
        print(f"'{test_prompt}' -> {spec.logic_type}: {spec.target}")
    else:
        print(f"'{test_prompt}' -> No match")