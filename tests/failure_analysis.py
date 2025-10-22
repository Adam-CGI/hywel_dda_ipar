#!/usr/bin/env python3
"""
Test Failure Analysis and Debugging Procedures

This script provides automated analysis of test failures and debugging assistance.
It helps identify patterns in test failures, suggests fixes, and tracks flaky tests.

Usage:
    python tests/failure_analysis.py [--analyze-failures] [--track-flaky] [--suggest-fixes]
"""

import json
import re
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict, Counter
import xml.etree.ElementTree as ET


class TestFailureAnalyzer:
    """Analyzes test failures and provides debugging assistance."""
    
    def __init__(self, project_root: Path = None):
        self.project_root = project_root or Path.cwd()
        self.failure_db_path = self.project_root / "tests" / "metrics" / "failure_history.json"
        self.failure_db_path.parent.mkdir(exist_ok=True)
        
        # Load historical failure data
        self.failure_history = self._load_failure_history()
        
        # Common failure patterns and their solutions
        self.failure_patterns = {
            "import_error": {
                "pattern": r"ImportError|ModuleNotFoundError",
                "solutions": [
                    "Check if the module path is correct",
                    "Verify the module is installed in the virtual environment",
                    "Check for circular imports",
                    "Ensure __init__.py files are present in package directories"
                ]
            },
            "attribute_error": {
                "pattern": r"AttributeError.*has no attribute",
                "solutions": [
                    "Check if the attribute name is spelled correctly",
                    "Verify the object type matches expectations",
                    "Check if the attribute exists in the current version",
                    "Review mock object configuration"
                ]
            },
            "assertion_error": {
                "pattern": r"AssertionError|assert .* == .*",
                "solutions": [
                    "Review the expected vs actual values",
                    "Check if the test data is correct",
                    "Verify the implementation logic",
                    "Consider floating-point precision issues"
                ]
            },
            "timeout_error": {
                "pattern": r"TimeoutError|timeout",
                "solutions": [
                    "Increase timeout values for slow operations",
                    "Optimize the code being tested",
                    "Check for infinite loops or blocking operations",
                    "Use async/await patterns where appropriate"
                ]
            },
            "mock_error": {
                "pattern": r"Mock|MagicMock.*side_effect|return_value",
                "solutions": [
                    "Check mock configuration and setup",
                    "Verify mock is applied to the correct target",
                    "Review mock call expectations",
                    "Ensure mock cleanup between tests"
                ]
            },
            "fixture_error": {
                "pattern": r"fixture.*not found|fixture.*error",
                "solutions": [
                    "Check fixture name spelling",
                    "Verify fixture is defined in conftest.py or test file",
                    "Check fixture scope (function, class, module, session)",
                    "Review fixture dependencies"
                ]
            },
            "database_error": {
                "pattern": r"DatabaseError|IntegrityError|OperationalError",
                "solutions": [
                    "Check database connection and credentials",
                    "Verify test database setup and cleanup",
                    "Review transaction handling in tests",
                    "Check for database schema issues"
                ]
            },
            "network_error": {
                "pattern": r"ConnectionError|HTTPError|RequestException",
                "solutions": [
                    "Check network connectivity",
                    "Verify API endpoints and credentials",
                    "Review mock configuration for external services",
                    "Add retry logic for flaky network operations"
                ]
            }
        }
    
    def _load_failure_history(self) -> Dict[str, Any]:
        """Load historical failure data from JSON file."""
        if self.failure_db_path.exists():
            try:
                with open(self.failure_db_path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        
        return {
            "failures": [],
            "flaky_tests": {},
            "patterns": {},
            "last_updated": None
        }
    
    def _save_failure_history(self):
        """Save failure history to JSON file."""
        self.failure_history["last_updated"] = datetime.now().isoformat()
        
        with open(self.failure_db_path, 'w') as f:
            json.dump(self.failure_history, f, indent=2)
    
    def analyze_current_failures(self) -> Dict[str, Any]:
        """Analyze current test failures from latest test run."""
        print("Analyzing current test failures...")
        
        # Parse JUnit XML for failures
        junit_file = self.project_root / "test-results.xml"
        if not junit_file.exists():
            print("No test results found. Run tests first.")
            return {"failures": [], "analysis": {}}
        
        failures = self._parse_junit_failures(junit_file)
        
        # Analyze failure patterns
        analysis = self._analyze_failure_patterns(failures)
        
        # Update failure history
        self._update_failure_history(failures)
        
        return {
            "failures": failures,
            "analysis": analysis,
            "timestamp": datetime.now().isoformat()
        }
    
    def _parse_junit_failures(self, junit_file: Path) -> List[Dict[str, Any]]:
        """Parse JUnit XML file to extract failure information."""
        failures = []
        
        try:
            tree = ET.parse(junit_file)
            root = tree.getroot()
            
            for testcase in root.findall(".//testcase"):
                failure_elem = testcase.find("failure")
                error_elem = testcase.find("error")
                
                if failure_elem is not None or error_elem is not None:
                    elem = failure_elem if failure_elem is not None else error_elem
                    
                    failure = {
                        "test_name": testcase.get("name"),
                        "test_class": testcase.get("classname"),
                        "test_file": self._extract_test_file(testcase.get("classname", "")),
                        "failure_type": "failure" if failure_elem is not None else "error",
                        "message": elem.get("message", ""),
                        "traceback": elem.text or "",
                        "execution_time": float(testcase.get("time", 0)),
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    failures.append(failure)
        
        except ET.ParseError as e:
            print(f"Error parsing JUnit XML: {e}")
        
        return failures
    
    def _extract_test_file(self, classname: str) -> str:
        """Extract test file path from test class name."""
        if not classname:
            return ""
        
        # Convert class name to file path
        # e.g., "tests.unit.test_service.TestClass" -> "tests/unit/test_service.py"
        parts = classname.split(".")
        if len(parts) >= 2:
            file_parts = parts[:-1]  # Remove class name
            return "/".join(file_parts) + ".py"
        
        return classname
    
    def _analyze_failure_patterns(self, failures: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze patterns in test failures."""
        analysis = {
            "total_failures": len(failures),
            "failure_types": Counter(),
            "common_patterns": [],
            "affected_files": Counter(),
            "suggested_fixes": []
        }
        
        for failure in failures:
            # Count failure types
            analysis["failure_types"][failure["failure_type"]] += 1
            
            # Count affected files
            analysis["affected_files"][failure["test_file"]] += 1
            
            # Analyze error patterns
            error_text = failure["message"] + " " + failure["traceback"]
            
            for pattern_name, pattern_info in self.failure_patterns.items():
                if re.search(pattern_info["pattern"], error_text, re.IGNORECASE):
                    analysis["common_patterns"].append({
                        "pattern": pattern_name,
                        "test": failure["test_name"],
                        "file": failure["test_file"],
                        "solutions": pattern_info["solutions"]
                    })
        
        # Generate overall suggestions
        analysis["suggested_fixes"] = self._generate_fix_suggestions(analysis)
        
        return analysis
    
    def _generate_fix_suggestions(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate fix suggestions based on failure analysis."""
        suggestions = []
        
        # Suggestions based on failure counts
        if analysis["total_failures"] > 10:
            suggestions.append("High number of failures detected. Consider running tests in smaller batches to isolate issues.")
        
        # Suggestions based on affected files
        most_affected = analysis["affected_files"].most_common(3)
        if most_affected:
            for file_path, count in most_affected:
                if count > 3:
                    suggestions.append(f"File {file_path} has {count} failing tests. Review this file for systematic issues.")
        
        # Suggestions based on common patterns
        pattern_counts = Counter(p["pattern"] for p in analysis["common_patterns"])
        for pattern, count in pattern_counts.most_common(3):
            if count > 2:
                suggestions.append(f"Multiple {pattern} errors detected. Review {pattern} handling across the codebase.")
        
        return suggestions
    
    def _update_failure_history(self, current_failures: List[Dict[str, Any]]):
        """Update failure history with current failures."""
        # Add current failures to history
        self.failure_history["failures"].extend(current_failures)
        
        # Keep only last 30 days of failures
        cutoff_date = datetime.now() - timedelta(days=30)
        self.failure_history["failures"] = [
            f for f in self.failure_history["failures"]
            if datetime.fromisoformat(f["timestamp"]) > cutoff_date
        ]
        
        # Update flaky test tracking
        self._update_flaky_tests(current_failures)
        
        # Save updated history
        self._save_failure_history()
    
    def _update_flaky_tests(self, current_failures: List[Dict[str, Any]]):
        """Update flaky test tracking."""
        # Track tests that fail intermittently
        for failure in current_failures:
            test_key = f"{failure['test_file']}::{failure['test_class']}::{failure['test_name']}"
            
            if test_key not in self.failure_history["flaky_tests"]:
                self.failure_history["flaky_tests"][test_key] = {
                    "failure_count": 0,
                    "total_runs": 0,
                    "first_failure": failure["timestamp"],
                    "last_failure": failure["timestamp"],
                    "failure_messages": []
                }
            
            flaky_info = self.failure_history["flaky_tests"][test_key]
            flaky_info["failure_count"] += 1
            flaky_info["total_runs"] += 1
            flaky_info["last_failure"] = failure["timestamp"]
            
            # Keep track of different failure messages
            if failure["message"] not in flaky_info["failure_messages"]:
                flaky_info["failure_messages"].append(failure["message"])
    
    def identify_flaky_tests(self, min_runs: int = 5, max_failure_rate: float = 0.3) -> List[Dict[str, Any]]:
        """Identify potentially flaky tests based on failure history."""
        flaky_tests = []
        
        for test_key, test_info in self.failure_history["flaky_tests"].items():
            if test_info["total_runs"] >= min_runs:
                failure_rate = test_info["failure_count"] / test_info["total_runs"]
                
                if 0 < failure_rate <= max_failure_rate:  # Not always failing, but failing sometimes
                    flaky_tests.append({
                        "test": test_key,
                        "failure_rate": failure_rate,
                        "failure_count": test_info["failure_count"],
                        "total_runs": test_info["total_runs"],
                        "first_failure": test_info["first_failure"],
                        "last_failure": test_info["last_failure"],
                        "unique_failures": len(test_info["failure_messages"])
                    })
        
        # Sort by failure rate (descending)
        flaky_tests.sort(key=lambda x: x["failure_rate"], reverse=True)
        
        return flaky_tests
    
    def generate_debugging_guide(self, failure: Dict[str, Any]) -> str:
        """Generate a debugging guide for a specific failure."""
        guide_lines = [
            f"# Debugging Guide: {failure['test_name']}",
            "",
            f"**Test File**: {failure['test_file']}",
            f"**Test Class**: {failure['test_class']}",
            f"**Failure Type**: {failure['failure_type']}",
            f"**Execution Time**: {failure['execution_time']:.3f}s",
            "",
            "## Error Message",
            "```",
            failure['message'],
            "```",
            "",
            "## Traceback",
            "```",
            failure['traceback'],
            "```",
            ""
        ]
        
        # Add pattern-specific debugging steps
        error_text = failure["message"] + " " + failure["traceback"]
        
        for pattern_name, pattern_info in self.failure_patterns.items():
            if re.search(pattern_info["pattern"], error_text, re.IGNORECASE):
                guide_lines.extend([
                    f"## Detected Pattern: {pattern_name.replace('_', ' ').title()}",
                    "",
                    "### Suggested Solutions:",
                ])
                
                for i, solution in enumerate(pattern_info["solutions"], 1):
                    guide_lines.append(f"{i}. {solution}")
                
                guide_lines.append("")
                break
        
        # Add general debugging steps
        guide_lines.extend([
            "## General Debugging Steps",
            "",
            "1. **Reproduce the failure locally**:",
            f"   ```bash",
            f"   pytest {failure['test_file']}::{failure['test_class']}::{failure['test_name']} -v",
            f"   ```",
            "",
            "2. **Run with increased verbosity**:",
            f"   ```bash",
            f"   pytest {failure['test_file']}::{failure['test_class']}::{failure['test_name']} -vvv -s",
            f"   ```",
            "",
            "3. **Check test isolation**:",
            f"   ```bash",
            f"   pytest {failure['test_file']}::{failure['test_class']}::{failure['test_name']} --lf",
            f"   ```",
            "",
            "4. **Review recent changes**:",
            "   - Check git history for recent modifications to the test or related code",
            "   - Review any dependency updates that might affect the test",
            "",
            "5. **Check test environment**:",
            "   - Verify all required dependencies are installed",
            "   - Check environment variables and configuration",
            "   - Ensure test data and fixtures are properly set up",
            ""
        ])
        
        return "\n".join(guide_lines)
    
    def generate_failure_report(self, analysis: Dict[str, Any]) -> str:
        """Generate a comprehensive failure analysis report."""
        report_lines = [
            "# Test Failure Analysis Report",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"## Summary",
            f"- **Total Failures**: {analysis['analysis']['total_failures']}",
            ""
        ]
        
        # Failure types breakdown
        if analysis['analysis']['failure_types']:
            report_lines.extend([
                "## Failure Types",
                ""
            ])
            
            for failure_type, count in analysis['analysis']['failure_types'].items():
                report_lines.append(f"- **{failure_type.title()}**: {count}")
            
            report_lines.append("")
        
        # Most affected files
        if analysis['analysis']['affected_files']:
            report_lines.extend([
                "## Most Affected Files",
                ""
            ])
            
            for file_path, count in analysis['analysis']['affected_files'].most_common(5):
                report_lines.append(f"- **{file_path}**: {count} failures")
            
            report_lines.append("")
        
        # Common patterns
        if analysis['analysis']['common_patterns']:
            report_lines.extend([
                "## Common Failure Patterns",
                ""
            ])
            
            pattern_groups = defaultdict(list)
            for pattern in analysis['analysis']['common_patterns']:
                pattern_groups[pattern['pattern']].append(pattern)
            
            for pattern_name, patterns in pattern_groups.items():
                report_lines.extend([
                    f"### {pattern_name.replace('_', ' ').title()} ({len(patterns)} occurrences)",
                    ""
                ])
                
                for pattern in patterns[:3]:  # Show first 3 occurrences
                    report_lines.append(f"- {pattern['test']} in {pattern['file']}")
                
                if len(patterns) > 3:
                    report_lines.append(f"- ... and {len(patterns) - 3} more")
                
                report_lines.extend([
                    "",
                    "**Suggested Solutions**:",
                ])
                
                for i, solution in enumerate(patterns[0]['solutions'], 1):
                    report_lines.append(f"{i}. {solution}")
                
                report_lines.append("")
        
        # Fix suggestions
        if analysis['analysis']['suggested_fixes']:
            report_lines.extend([
                "## Recommended Actions",
                ""
            ])
            
            for i, suggestion in enumerate(analysis['analysis']['suggested_fixes'], 1):
                report_lines.append(f"{i}. {suggestion}")
            
            report_lines.append("")
        
        # Individual failures
        if analysis['failures']:
            report_lines.extend([
                "## Individual Failures",
                ""
            ])
            
            for failure in analysis['failures'][:10]:  # Show first 10 failures
                report_lines.extend([
                    f"### {failure['test_name']}",
                    f"- **File**: {failure['test_file']}",
                    f"- **Type**: {failure['failure_type']}",
                    f"- **Time**: {failure['execution_time']:.3f}s",
                    f"- **Message**: {failure['message'][:100]}{'...' if len(failure['message']) > 100 else ''}",
                    ""
                ])
        
        return "\n".join(report_lines)


def main():
    """Main entry point for failure analysis."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Failure Analysis and Debugging")
    parser.add_argument("--analyze-failures", action="store_true", help="Analyze current test failures")
    parser.add_argument("--track-flaky", action="store_true", help="Identify flaky tests")
    parser.add_argument("--suggest-fixes", action="store_true", help="Generate fix suggestions")
    parser.add_argument("--debug-test", help="Generate debugging guide for specific test")
    parser.add_argument("--output-dir", help="Output directory for reports")
    
    args = parser.parse_args()
    
    # Initialize analyzer
    project_root = Path.cwd()
    if args.output_dir:
        project_root = Path(args.output_dir)
    
    analyzer = TestFailureAnalyzer(project_root)
    
    if args.analyze_failures:
        # Analyze current failures
        analysis = analyzer.analyze_current_failures()
        
        if analysis["failures"]:
            print(f"Found {len(analysis['failures'])} test failures")
            
            # Generate and save report
            report = analyzer.generate_failure_report(analysis)
            
            report_file = analyzer.failure_db_path.parent / f"failure_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            with open(report_file, 'w') as f:
                f.write(report)
            
            print(f"Failure report saved to: {report_file}")
            
            if args.suggest_fixes:
                print("\n🔧 Suggested Fixes:")
                for i, suggestion in enumerate(analysis["analysis"]["suggested_fixes"], 1):
                    print(f"  {i}. {suggestion}")
        else:
            print("✅ No test failures found")
    
    if args.track_flaky:
        # Identify flaky tests
        flaky_tests = analyzer.identify_flaky_tests()
        
        if flaky_tests:
            print(f"\n🔄 Found {len(flaky_tests)} potentially flaky tests:")
            
            for test in flaky_tests[:5]:  # Show top 5
                print(f"  - {test['test']}")
                print(f"    Failure rate: {test['failure_rate']:.1%} ({test['failure_count']}/{test['total_runs']} runs)")
                print(f"    Unique failure types: {test['unique_failures']}")
                print()
        else:
            print("✅ No flaky tests detected")
    
    if args.debug_test:
        # Generate debugging guide for specific test
        # This would need to find the test in recent failures
        print(f"Generating debugging guide for: {args.debug_test}")
        # Implementation would search failure history for the specified test


if __name__ == "__main__":
    main()