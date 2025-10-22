#!/usr/bin/env python3
"""
Test Quality Metrics and Monitoring Script

This script provides comprehensive test quality metrics including:
- Coverage analysis and trend monitoring
- Test performance tracking and optimization
- Test failure analysis and debugging procedures
- Test reliability metrics

Usage:
    python tests/test_metrics.py [--generate-report] [--check-thresholds]
"""

import json
import time
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import xml.etree.ElementTree as ET


class TestMetrics:
    """Test quality metrics collector and analyzer."""
    
    def __init__(self, project_root: Path = None):
        self.project_root = project_root or Path.cwd()
        self.metrics_dir = self.project_root / "tests" / "metrics"
        self.metrics_dir.mkdir(exist_ok=True)
        
        # Quality thresholds
        self.thresholds = {
            "coverage": {
                "total": 80.0,
                "service_layer": 90.0,
                "critical_paths": 100.0
            },
            "performance": {
                "unit_test_max_time": 0.1,  # 100ms per unit test
                "integration_test_max_time": 1.0,  # 1s per integration test
                "system_test_max_time": 10.0,  # 10s per system test
                "total_suite_max_time": 300.0  # 5 minutes total
            },
            "reliability": {
                "max_flaky_rate": 0.01,  # 1% flaky test rate
                "min_success_rate": 0.99  # 99% success rate
            }
        }
    
    def run_tests_with_metrics(self) -> Dict[str, Any]:
        """Run complete test suite and collect metrics."""
        print("Running test suite with metrics collection...")
        
        start_time = time.time()
        
        # Run tests with coverage and timing
        cmd = [
            "pytest", 
            "tests/",
            "--cov=app",
            "--cov-report=xml",
            "--cov-report=html",
            "--cov-report=term-missing",
            "--junit-xml=test-results.xml",
            "-v",
            "--durations=0"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.project_root)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Parse results
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "total_execution_time": total_time,
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
        
        # Parse coverage data
        coverage_data = self._parse_coverage_xml()
        if coverage_data:
            metrics["coverage"] = coverage_data
        
        # Parse test results
        test_results = self._parse_junit_xml()
        if test_results:
            metrics["test_results"] = test_results
        
        # Parse performance data
        performance_data = self._parse_performance_data(result.stdout)
        if performance_data:
            metrics["performance"] = performance_data
        
        return metrics
    
    def _parse_coverage_xml(self) -> Optional[Dict[str, Any]]:
        """Parse coverage.xml file for detailed coverage metrics."""
        coverage_file = self.project_root / "coverage.xml"
        if not coverage_file.exists():
            return None
        
        try:
            tree = ET.parse(coverage_file)
            root = tree.getroot()
            
            coverage_data = {
                "total_statements": 0,
                "covered_statements": 0,
                "total_branches": 0,
                "covered_branches": 0,
                "files": {}
            }
            
            for package in root.findall(".//package"):
                for class_elem in package.findall("classes/class"):
                    filename = class_elem.get("filename", "")
                    
                    # Get line coverage
                    lines = class_elem.findall("lines/line")
                    total_lines = len(lines)
                    covered_lines = len([line for line in lines if line.get("hits", "0") != "0"])
                    
                    # Get branch coverage
                    branches = [line for line in lines if line.get("branch") == "true"]
                    total_branches = len(branches)
                    covered_branches = len([branch for branch in branches if branch.get("condition-coverage", "0%").split()[0] != "0%"])
                    
                    coverage_data["files"][filename] = {
                        "line_coverage": (covered_lines / total_lines * 100) if total_lines > 0 else 0,
                        "branch_coverage": (covered_branches / total_branches * 100) if total_branches > 0 else 0,
                        "total_lines": total_lines,
                        "covered_lines": covered_lines,
                        "total_branches": total_branches,
                        "covered_branches": covered_branches
                    }
                    
                    coverage_data["total_statements"] += total_lines
                    coverage_data["covered_statements"] += covered_lines
                    coverage_data["total_branches"] += total_branches
                    coverage_data["covered_branches"] += covered_branches
            
            # Calculate overall percentages
            coverage_data["line_coverage_percent"] = (
                coverage_data["covered_statements"] / coverage_data["total_statements"] * 100
                if coverage_data["total_statements"] > 0 else 0
            )
            coverage_data["branch_coverage_percent"] = (
                coverage_data["covered_branches"] / coverage_data["total_branches"] * 100
                if coverage_data["total_branches"] > 0 else 0
            )
            
            return coverage_data
            
        except Exception as e:
            print(f"Error parsing coverage XML: {e}")
            return None
    
    def _parse_junit_xml(self) -> Optional[Dict[str, Any]]:
        """Parse test-results.xml for test execution metrics."""
        junit_file = self.project_root / "test-results.xml"
        if not junit_file.exists():
            return None
        
        try:
            tree = ET.parse(junit_file)
            root = tree.getroot()
            
            test_results = {
                "total_tests": int(root.get("tests", 0)),
                "passed_tests": 0,
                "failed_tests": int(root.get("failures", 0)),
                "error_tests": int(root.get("errors", 0)),
                "skipped_tests": int(root.get("skipped", 0)),
                "execution_time": float(root.get("time", 0)),
                "test_cases": []
            }
            
            test_results["passed_tests"] = (
                test_results["total_tests"] - 
                test_results["failed_tests"] - 
                test_results["error_tests"] - 
                test_results["skipped_tests"]
            )
            
            # Parse individual test cases
            for testcase in root.findall(".//testcase"):
                case_data = {
                    "name": testcase.get("name"),
                    "classname": testcase.get("classname"),
                    "time": float(testcase.get("time", 0)),
                    "status": "passed"
                }
                
                if testcase.find("failure") is not None:
                    case_data["status"] = "failed"
                    case_data["failure_message"] = testcase.find("failure").text
                elif testcase.find("error") is not None:
                    case_data["status"] = "error"
                    case_data["error_message"] = testcase.find("error").text
                elif testcase.find("skipped") is not None:
                    case_data["status"] = "skipped"
                
                test_results["test_cases"].append(case_data)
            
            # Calculate success rate
            test_results["success_rate"] = (
                test_results["passed_tests"] / test_results["total_tests"]
                if test_results["total_tests"] > 0 else 0
            )
            
            return test_results
            
        except Exception as e:
            print(f"Error parsing JUnit XML: {e}")
            return None
    
    def _parse_performance_data(self, stdout: str) -> Optional[Dict[str, Any]]:
        """Parse performance data from pytest output."""
        lines = stdout.split('\n')
        
        # Look for slowest durations section
        durations_start = None
        for i, line in enumerate(lines):
            if "slowest" in line.lower() and "durations" in line.lower():
                durations_start = i + 1
                break
        
        if durations_start is None:
            return None
        
        performance_data = {
            "slowest_tests": [],
            "unit_test_times": [],
            "integration_test_times": [],
            "system_test_times": []
        }
        
        # Parse slowest tests
        for i in range(durations_start, min(durations_start + 20, len(lines))):
            line = lines[i].strip()
            if not line or "=" in line:
                break
            
            # Parse format: "0.25s call tests/unit/test_file.py::TestClass::test_method"
            parts = line.split()
            if len(parts) >= 3:
                time_str = parts[0]
                if time_str.endswith('s'):
                    try:
                        test_time = float(time_str[:-1])
                        test_path = parts[-1]
                        
                        performance_data["slowest_tests"].append({
                            "test": test_path,
                            "time": test_time
                        })
                        
                        # Categorize by test type
                        if "/unit/" in test_path:
                            performance_data["unit_test_times"].append(test_time)
                        elif "/integration/" in test_path:
                            performance_data["integration_test_times"].append(test_time)
                        elif "/system/" in test_path:
                            performance_data["system_test_times"].append(test_time)
                            
                    except ValueError:
                        continue
        
        # Calculate statistics
        for test_type in ["unit_test_times", "integration_test_times", "system_test_times"]:
            times = performance_data[test_type]
            if times:
                performance_data[f"{test_type}_stats"] = {
                    "count": len(times),
                    "min": min(times),
                    "max": max(times),
                    "avg": sum(times) / len(times),
                    "total": sum(times)
                }
        
        return performance_data
    
    def analyze_quality_metrics(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze metrics against quality thresholds."""
        analysis = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "PASS",
            "issues": [],
            "recommendations": []
        }
        
        # Coverage analysis
        if "coverage" in metrics:
            coverage = metrics["coverage"]
            
            if coverage["line_coverage_percent"] < self.thresholds["coverage"]["total"]:
                analysis["issues"].append({
                    "type": "coverage",
                    "severity": "high",
                    "message": f"Total coverage {coverage['line_coverage_percent']:.1f}% below threshold {self.thresholds['coverage']['total']}%"
                })
                analysis["overall_status"] = "FAIL"
            
            # Check service layer coverage
            service_files = [f for f in coverage["files"] if "services/" in f]
            if service_files:
                service_coverage = sum(coverage["files"][f]["line_coverage"] for f in service_files) / len(service_files)
                if service_coverage < self.thresholds["coverage"]["service_layer"]:
                    analysis["issues"].append({
                        "type": "coverage",
                        "severity": "medium",
                        "message": f"Service layer coverage {service_coverage:.1f}% below threshold {self.thresholds['coverage']['service_layer']}%"
                    })
        
        # Performance analysis
        if "performance" in metrics:
            perf = metrics["performance"]
            
            # Check unit test performance
            if "unit_test_times_stats" in perf:
                max_unit_time = perf["unit_test_times_stats"]["max"]
                if max_unit_time > self.thresholds["performance"]["unit_test_max_time"]:
                    analysis["issues"].append({
                        "type": "performance",
                        "severity": "medium",
                        "message": f"Slowest unit test {max_unit_time:.3f}s exceeds threshold {self.thresholds['performance']['unit_test_max_time']}s"
                    })
        
        # Test results analysis
        if "test_results" in metrics:
            results = metrics["test_results"]
            
            if results["success_rate"] < self.thresholds["reliability"]["min_success_rate"]:
                analysis["issues"].append({
                    "type": "reliability",
                    "severity": "high",
                    "message": f"Test success rate {results['success_rate']:.1%} below threshold {self.thresholds['reliability']['min_success_rate']:.1%}"
                })
                analysis["overall_status"] = "FAIL"
        
        # Generate recommendations
        if analysis["issues"]:
            analysis["recommendations"] = self._generate_recommendations(analysis["issues"])
        
        return analysis
    
    def _generate_recommendations(self, issues: List[Dict[str, Any]]) -> List[str]:
        """Generate actionable recommendations based on issues."""
        recommendations = []
        
        coverage_issues = [i for i in issues if i["type"] == "coverage"]
        performance_issues = [i for i in issues if i["type"] == "performance"]
        reliability_issues = [i for i in issues if i["type"] == "reliability"]
        
        if coverage_issues:
            recommendations.extend([
                "Add unit tests for uncovered service methods",
                "Focus on testing error handling and edge cases",
                "Consider adding integration tests for multi-service workflows",
                "Review and test critical business logic paths"
            ])
        
        if performance_issues:
            recommendations.extend([
                "Optimize slow unit tests by reducing setup complexity",
                "Use more focused mocking to avoid expensive operations",
                "Consider parallelizing independent test execution",
                "Profile and optimize test fixtures and utilities"
            ])
        
        if reliability_issues:
            recommendations.extend([
                "Investigate and fix failing tests immediately",
                "Review test isolation and cleanup procedures",
                "Add retry mechanisms for flaky external dependencies",
                "Improve test data management and consistency"
            ])
        
        return recommendations
    
    def save_metrics(self, metrics: Dict[str, Any], analysis: Dict[str, Any]):
        """Save metrics and analysis to files."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save detailed metrics
        metrics_file = self.metrics_dir / f"test_metrics_{timestamp}.json"
        with open(metrics_file, 'w', encoding='utf-8') as f:
            json.dump(metrics, f, indent=2)
        
        # Save analysis
        analysis_file = self.metrics_dir / f"test_analysis_{timestamp}.json"
        with open(analysis_file, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2)
        
        # Update latest metrics
        latest_metrics = self.metrics_dir / "latest_metrics.json"
        with open(latest_metrics, 'w', encoding='utf-8') as f:
            json.dump({"metrics": metrics, "analysis": analysis}, f, indent=2)
        
        print(f"Metrics saved to {metrics_file}")
        print(f"Analysis saved to {analysis_file}")
    
    def generate_report(self, metrics: Dict[str, Any], analysis: Dict[str, Any]) -> str:
        """Generate a comprehensive test quality report."""
        report_lines = [
            "# Test Quality Report",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"## Overall Status: {analysis['overall_status']}",
            ""
        ]
        
        # Coverage summary
        if "coverage" in metrics:
            cov = metrics["coverage"]
            report_lines.extend([
                "## Coverage Summary",
                f"- **Total Coverage**: {cov['line_coverage_percent']:.1f}%",
                f"- **Branch Coverage**: {cov['branch_coverage_percent']:.1f}%",
                f"- **Statements**: {cov['covered_statements']}/{cov['total_statements']}",
                f"- **Branches**: {cov['covered_branches']}/{cov['total_branches']}",
                ""
            ])
        
        # Test execution summary
        if "test_results" in metrics:
            results = metrics["test_results"]
            report_lines.extend([
                "## Test Execution Summary",
                f"- **Total Tests**: {results['total_tests']}",
                f"- **Passed**: {results['passed_tests']}",
                f"- **Failed**: {results['failed_tests']}",
                f"- **Errors**: {results['error_tests']}",
                f"- **Skipped**: {results['skipped_tests']}",
                f"- **Success Rate**: {results['success_rate']:.1%}",
                f"- **Execution Time**: {results['execution_time']:.2f}s",
                ""
            ])
        
        # Performance summary
        if "performance" in metrics:
            perf = metrics["performance"]
            report_lines.extend([
                "## Performance Summary",
            ])
            
            for test_type in ["unit", "integration", "system"]:
                stats_key = f"{test_type}_test_times_stats"
                if stats_key in perf:
                    stats = perf[stats_key]
                    report_lines.extend([
                        f"### {test_type.title()} Tests",
                        f"- **Count**: {stats['count']}",
                        f"- **Average Time**: {stats['avg']:.3f}s",
                        f"- **Slowest**: {stats['max']:.3f}s",
                        f"- **Total Time**: {stats['total']:.3f}s",
                        ""
                    ])
        
        # Issues and recommendations
        if analysis["issues"]:
            report_lines.extend([
                "## Issues Found",
                ""
            ])
            
            for issue in analysis["issues"]:
                report_lines.append(f"- **{issue['severity'].upper()}**: {issue['message']}")
            
            report_lines.append("")
        
        if analysis["recommendations"]:
            report_lines.extend([
                "## Recommendations",
                ""
            ])
            
            for rec in analysis["recommendations"]:
                report_lines.append(f"- {rec}")
            
            report_lines.append("")
        
        # Quality thresholds
        report_lines.extend([
            "## Quality Thresholds",
            "### Coverage",
            f"- Total Coverage: >={self.thresholds['coverage']['total']}%",
            f"- Service Layer: >={self.thresholds['coverage']['service_layer']}%",
            f"- Critical Paths: >={self.thresholds['coverage']['critical_paths']}%",
            "",
            "### Performance",
            f"- Unit Test Max Time: <={self.thresholds['performance']['unit_test_max_time']}s",
            f"- Integration Test Max Time: <={self.thresholds['performance']['integration_test_max_time']}s",
            f"- System Test Max Time: <={self.thresholds['performance']['system_test_max_time']}s",
            f"- Total Suite Max Time: <={self.thresholds['performance']['total_suite_max_time']}s",
            "",
            "### Reliability",
            f"- Max Flaky Rate: <={self.thresholds['reliability']['max_flaky_rate']:.1%}",
            f"- Min Success Rate: >={self.thresholds['reliability']['min_success_rate']:.1%}",
            ""
        ])
        
        return "\n".join(report_lines)


def main():
    """Main entry point for test metrics collection."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Quality Metrics and Monitoring")
    parser.add_argument("--generate-report", action="store_true", help="Generate and save test quality report")
    parser.add_argument("--check-thresholds", action="store_true", help="Check metrics against quality thresholds")
    parser.add_argument("--output-dir", help="Output directory for reports")
    
    args = parser.parse_args()
    
    # Initialize metrics collector
    project_root = Path.cwd()
    if args.output_dir:
        project_root = Path(args.output_dir)
    
    metrics_collector = TestMetrics(project_root)
    
    # Run tests and collect metrics
    print("Collecting test metrics...")
    metrics = metrics_collector.run_tests_with_metrics()
    
    # Analyze metrics
    print("Analyzing quality metrics...")
    analysis = metrics_collector.analyze_quality_metrics(metrics)
    
    # Save metrics
    metrics_collector.save_metrics(metrics, analysis)
    
    # Generate report if requested
    if args.generate_report:
        report = metrics_collector.generate_report(metrics, analysis)
        
        report_file = metrics_collector.metrics_dir / f"test_quality_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"Report generated: {report_file}")
        print("\n" + "="*50)
        print(report)
    
    # Check thresholds and exit with appropriate code
    if args.check_thresholds:
        if analysis["overall_status"] == "FAIL":
            print(f"\n❌ Quality thresholds not met. Found {len(analysis['issues'])} issues.")
            for issue in analysis["issues"]:
                print(f"  - {issue['severity'].upper()}: {issue['message']}")
            sys.exit(1)
        else:
            print("\n✅ All quality thresholds met.")
            sys.exit(0)
    
    # Print summary
    print(f"\n📊 Test Metrics Summary:")
    print(f"   Status: {analysis['overall_status']}")
    if "coverage" in metrics:
        print(f"   Coverage: {metrics['coverage']['line_coverage_percent']:.1f}%")
    if "test_results" in metrics:
        print(f"   Tests: {metrics['test_results']['passed_tests']}/{metrics['test_results']['total_tests']} passed")
        print(f"   Success Rate: {metrics['test_results']['success_rate']:.1%}")
    if analysis["issues"]:
        print(f"   Issues: {len(analysis['issues'])}")


if __name__ == "__main__":
    main()