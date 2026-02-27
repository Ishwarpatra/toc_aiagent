import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '.'))

from core.models import LogicSpec

# Test the semantic normalizer with various inputs
test_prompts = [
    'strings that start with ab',
    'strings beginning with ab', 
    'strings having prefix ab',
    'In binary system, strings that end with 01',
    'For alphabet {a,b}, strings containing ba'
]

print('Testing semantic normalization:')
for prompt in test_prompts:
    print(f'Input: {prompt}')
    spec = LogicSpec.from_prompt(prompt)
    if spec:
        print(f'  -> LogicType: {spec.logic_type}, Target: {spec.target}, Alphabet: {spec.alphabet}')
    else:
        print('  -> No match found')
    print()