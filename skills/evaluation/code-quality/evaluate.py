#!/usr/bin/env python3
"""
Code Quality Evaluation
"""

import ast
import re
from typing import Dict, List, Any


class CodeQualityEvaluator:
    """Evaluate code quality metrics."""
    
    def __init__(self):
        self.metrics = {}
    
    def evaluate_file(self, filepath: str) -> Dict[str, Any]:
        """Evaluate a single file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        results = {
            "file": filepath,
            "lines": len(content.split('\n')),
            "complexity": self._calculate_complexity(content),
            "documentation": self._check_documentation(content),
            "security": self._check_security(content),
            "style": self._check_style(content),
        }
        
        return results
    
    def _calculate_complexity(self, content: str) -> int:
        """Calculate cyclomatic complexity."""
        try:
            tree = ast.parse(content)
            complexity = 1
            for node in ast.walk(tree):
                if isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                    complexity += 1
            return complexity
        except:
            return -1
    
    def _check_documentation(self, content: str) -> Dict[str, Any]:
        """Check documentation coverage."""
        lines = content.split('\n')
        doc_lines = sum(1 for line in lines if line.strip().startswith('#') or '"""' in line or "'''" in line)
        total_lines = len(lines)
        
        return {
            "doc_lines": doc_lines,
            "total_lines": total_lines,
            "coverage": doc_lines / total_lines if total_lines > 0 else 0
        }
    
    def _check_security(self, content: str) -> List[str]:
        """Check for security issues."""
        issues = []
        
        # Check for common security patterns
        if "eval(" in content:
            issues.append("Use of eval() - potential code injection")
        if "exec(" in content:
            issues.append("Use of exec() - potential code injection")
        if "subprocess.call(shell=True" in content:
            issues.append("Shell=True in subprocess - potential command injection")
        if "pickle.load" in content:
            issues.append("Use of pickle.load() - potential deserialization attack")
        
        return issues
    
    def _check_style(self, content: str) -> Dict[str, Any]:
        """Check code style."""
        lines = content.split('\n')
        
        issues = []
        for i, line in enumerate(lines, 1):
            if len(line) > 120:
                issues.append(f"Line {i}: Line too long ({len(line)} chars)")
            if line.endswith(' ') or line.endswith('\t'):
                issues.append(f"Line {i}: Trailing whitespace")
        
        return {
            "issues": issues,
            "score": max(0, 100 - len(issues) * 5)
        }


def main():
    """CLI entry point."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python evaluate.py <filepath>")
        sys.exit(1)
    
    evaluator = CodeQualityEvaluator()
    results = evaluator.evaluate_file(sys.argv[1])
    
    print(f"File: {results['file']}")
    print(f"Lines: {results['lines']}")
    print(f"Complexity: {results['complexity']}")
    print(f"Documentation coverage: {results['documentation']['coverage']:.1%}")
    print(f"Security issues: {len(results['security'])}")
    print(f"Style score: {results['style']['score']}/100")


if __name__ == "__main__":
    main()
