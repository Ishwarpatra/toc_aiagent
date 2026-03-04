import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '.'))

from core.models import LogicSpec

# Test the semantic normalization
prompt = 'strings that start with ab'
print(f'Testing: {prompt}')
spec = LogicSpec.from_prompt(prompt)
if spec:
    print(f'Parsed as: {spec.logic_type}, target: {spec.target}, alphabet: {spec.alphabet}')
else:
    print('No match found')