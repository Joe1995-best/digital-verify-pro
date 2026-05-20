#!/usr/bin/env python3
"""Add deprecation warnings to parallel scripts"""
import os

for path in ['run_dma_convergence.py', 'run_e2e.py']:
    if not os.path.isfile(path):
        continue
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    if 'DEPRECATED' in lines[0] if lines else '':
        print(f'{path}: already deprecated')
        continue
    
    msg = 'use pro_verify.py --pipeline ot_dma_spec.yml' if 'dma' in path else 'use pro_verify.py --pipeline <spec>.yml'
    new_lines = [
        '"""DEPRECATED - ' + msg + '"""\n',
        'import warnings\n',
        'warnings.warn("' + path + ' is deprecated, ' + msg + '")\n',
        '\n',
    ]
    # Preserve shebang if exists
    if lines[0].startswith('#!'):
        first = lines[0]
        lines = lines[1:]
        new_lines.insert(0, first)
    
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines + lines)
    print(f'{path}: deprecation warning added')
