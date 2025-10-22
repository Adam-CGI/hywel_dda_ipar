#!/usr/bin/env python3
"""
Test Quality Dashboard

A simple web dashboard for monitoring test quality metrics, coverage trends,
and performance over time. Provides real-time insights into test suite health.

Usage:
    python tests/test_dashboard.py [--port 8080] [--host localhost]
"""

import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import subprocess


class TestDashboard:
    """Simple test quality dashboard generator."""
    
    def __init__(self, project_root: Path = None):
        self.project_root = project_root or Path.cwd()
        self.metrics_dir = self.project_root / "tests" / "metrics"
        self.metrics_dir.mkdir(exist_ok=True)
    
    def collect_latest_metrics(self) -> Dict[str, Any]:
        """Collect the latest test metrics."""
        latest_file = self.metrics_dir / "latest_metrics.json"
        
        if latest_file.exists():
            try:
                with open(latest_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        
        # If no metrics exist, run collection
        print("No recent metrics found. Collecting fresh metrics...")
        return self._run_fresh_metrics()
    
    def _run_fresh_metrics(self) -> Dict[str, Any]:
        """Run test metrics collection."""
        try:
            # Import and run metrics collection
            sys.path.insert(0, str(self.project_root / "tests"))
            from test_metrics import TestMetrics
            
            metrics_collector = TestMetrics(self.project_root)
            metrics = metrics_collector.run_tests_with_metrics()
            analysis = metrics_collector.analyze_quality_metrics(metrics)
            
            return {"metrics": metrics, "analysis": analysis}
        except Exception as e:
            print(f"Error collecting metrics: {e}")
            return {"metrics": {}, "analysis": {}}
    
    def get_historical_metrics(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get historical metrics for trend analysis."""
        historical = []
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Scan metrics directory for historical files
        for metrics_file in self.metrics_dir.glob("test_metrics_*.json"):
            try:
                # Extract timestamp from filename
                timestamp_str = metrics_file.stem.split("_", 2)[-1]
                file_date = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                
                if file_date > cutoff_date:
                    with open(metrics_file, 'r') as f:
                        metrics_data = json.load(f)
                        metrics_data["file_timestamp"] = file_date.isoformat()
                        historical.append(metrics_data)
            except (ValueError, json.JSONDecodeError, IOError):
                continue
        
        # Sort by timestamp
        historical.sort(key=lambda x: x.get("file_timestamp", ""))
        
        return historical
    
    def generate_html_dashboard(self) -> str:
        """Generate HTML dashboard."""
        latest_data = self.collect_latest_metrics()
        historical_data = self.get_historical_metrics()
        
        metrics = latest_data.get("metrics", {})
        analysis = latest_data.get("analysis", {})
        
        # Generate HTML
        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Quality Dashboard</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .header {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}
        .metric-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .metric-title {{
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 10px;
            color: #333;
        }}
        .metric-value {{
            font-size: 32px;
            font-weight: 700;
            margin-bottom: 5px;
        }}
        .metric-subtitle {{
            color: #666;
            font-size: 14px;
        }}
        .status-pass {{ color: #22c55e; }}
        .status-fail {{ color: #ef4444; }}
        .status-warning {{ color: #f59e0b; }}
        .progress-bar {{
            width: 100%;
            height: 8px;
            background-color: #e5e7eb;
            border-radius: 4px;
            overflow: hidden;
            margin: 10px 0;
        }}
        .progress-fill {{
            height: 100%;
            background-color: #22c55e;
            transition: width 0.3s ease;
        }}
        .issues-list {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        .issue-item {{
            padding: 10px;
            margin: 5px 0;
            border-left: 4px solid #ef4444;
            background-color: #fef2f2;
            border-radius: 0 4px 4px 0;
        }}
        .issue-high {{ border-left-color: #ef4444; background-color: #fef2f2; }}
        .issue-medium {{ border-left-color: #f59e0b; background-color: #fffbeb; }}
        .issue-low {{ border-left-color: #6b7280; background-color: #f9fafb; }}
        .recommendations {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .recommendation-item {{
            padding: 10px;
            margin: 5px 0;
            border-left: 4px solid #3b82f6;
            background-color: #eff6ff;
            border-radius: 0 4px 4px 0;
        }}
        .timestamp {{
            color: #666;
            font-size: 12px;
        }}
        .refresh-btn {{
            background: #3b82f6;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }}
        .refresh-btn:hover {{
            background: #2563eb;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Test Quality Dashboard</h1>
            <p class="timestamp">Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <button class="refresh-btn" onclick="location.reload()">Refresh Metrics</button>
        </div>
        
        <div class="metrics-grid">
            {self._generate_coverage_card(metrics)}
            {self._generate_test_results_card(metrics)}
            {self._generate_performance_card(metrics)}
            {self._generate_status_card(analysis)}
        </div>
        
        {self._generate_issues_section(analysis)}
        {self._generate_recommendations_section(analysis)}
        {self._generate_trends_section(historical_data)}
    </div>
    
    <script>
        // Auto-refresh every 5 minutes
        setTimeout(function() {{
            location.reload();
        }}, 300000);
    </script>
</body>
</html>
"""
        return html
    
    def _generate_coverage_card(self, metrics: Dict[str, Any]) -> str:
        """Generate coverage metrics card."""
        if "coverage" not in metrics:
            return """
            <div class="metric-card">
                <div class="metric-title">Coverage</div>
                <div class="metric-value status-warning">N/A</div>
                <div class="metric-subtitle">No coverage data available</div>
            </div>
            """
        
        coverage = metrics["coverage"]
        line_coverage = coverage.get("line_coverage_percent", 0)
        branch_coverage = coverage.get("branch_coverage_percent", 0)
        
        status_class = "status-pass" if line_coverage >= 80 else "status-warning" if line_coverage >= 60 else "status-fail"
        
        return f"""
        <div class="metric-card">
            <div class="metric-title">Coverage</div>
            <div class="metric-value {status_class}">{line_coverage:.1f}%</div>
            <div class="metric-subtitle">Line Coverage</div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: {line_coverage}%"></div>
            </div>
            <div class="metric-subtitle">
                Branch: {branch_coverage:.1f}% | 
                Lines: {coverage.get('covered_statements', 0)}/{coverage.get('total_statements', 0)}
            </div>
        </div>
        """
    
    def _generate_test_results_card(self, metrics: Dict[str, Any]) -> str:
        """Generate test results card."""
        if "test_results" not in metrics:
            return """
            <div class="metric-card">
                <div class="metric-title">Test Results</div>
                <div class="metric-value status-warning">N/A</div>
                <div class="metric-subtitle">No test results available</div>
            </div>
            """
        
        results = metrics["test_results"]
        success_rate = results.get("success_rate", 0) * 100
        total_tests = results.get("total_tests", 0)
        passed_tests = results.get("passed_tests", 0)
        failed_tests = results.get("failed_tests", 0)
        
        status_class = "status-pass" if success_rate >= 99 else "status-warning" if success_rate >= 95 else "status-fail"
        
        return f"""
        <div class="metric-card">
            <div class="metric-title">Test Results</div>
            <div class="metric-value {status_class}">{success_rate:.1f}%</div>
            <div class="metric-subtitle">Success Rate</div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: {success_rate}%"></div>
            </div>
            <div class="metric-subtitle">
                Passed: {passed_tests} | Failed: {failed_tests} | Total: {total_tests}
            </div>
        </div>
        """
    
    def _generate_performance_card(self, metrics: Dict[str, Any]) -> str:
        """Generate performance metrics card."""
        if "performance" not in metrics:
            return """
            <div class="metric-card">
                <div class="metric-title">Performance</div>
                <div class="metric-value status-warning">N/A</div>
                <div class="metric-subtitle">No performance data available</div>
            </div>
            """
        
        perf = metrics["performance"]
        total_time = metrics.get("total_execution_time", 0)
        
        # Get average unit test time
        avg_unit_time = 0
        if "unit_test_times_stats" in perf:
            avg_unit_time = perf["unit_test_times_stats"].get("avg", 0)
        
        status_class = "status-pass" if avg_unit_time < 0.1 else "status-warning" if avg_unit_time < 0.5 else "status-fail"
        
        return f"""
        <div class="metric-card">
            <div class="metric-title">Performance</div>
            <div class="metric-value {status_class}">{avg_unit_time:.3f}s</div>
            <div class="metric-subtitle">Avg Unit Test Time</div>
            <div class="metric-subtitle">
                Total Suite: {total_time:.1f}s | 
                Slowest Tests: {len(perf.get('slowest_tests', []))}
            </div>
        </div>
        """
    
    def _generate_status_card(self, analysis: Dict[str, Any]) -> str:
        """Generate overall status card."""
        if not analysis:
            return """
            <div class="metric-card">
                <div class="metric-title">Overall Status</div>
                <div class="metric-value status-warning">UNKNOWN</div>
                <div class="metric-subtitle">No analysis available</div>
            </div>
            """
        
        status = analysis.get("overall_status", "UNKNOWN")
        issues_count = len(analysis.get("issues", []))
        
        status_class = "status-pass" if status == "PASS" else "status-fail"
        
        return f"""
        <div class="metric-card">
            <div class="metric-title">Overall Status</div>
            <div class="metric-value {status_class}">{status}</div>
            <div class="metric-subtitle">Quality Gate</div>
            <div class="metric-subtitle">
                Issues Found: {issues_count}
            </div>
        </div>
        """
    
    def _generate_issues_section(self, analysis: Dict[str, Any]) -> str:
        """Generate issues section."""
        if not analysis or not analysis.get("issues"):
            return """
            <div class="issues-list">
                <div class="metric-title">Issues</div>
                <p style="color: #22c55e;">✅ No issues detected</p>
            </div>
            """
        
        issues_html = ['<div class="issues-list">', '<div class="metric-title">Issues Found</div>']
        
        for issue in analysis["issues"]:
            severity = issue.get("severity", "low")
            message = issue.get("message", "")
            issue_type = issue.get("type", "unknown")
            
            issues_html.append(f"""
            <div class="issue-item issue-{severity}">
                <strong>{severity.upper()}</strong> [{issue_type}]: {message}
            </div>
            """)
        
        issues_html.append('</div>')
        return ''.join(issues_html)
    
    def _generate_recommendations_section(self, analysis: Dict[str, Any]) -> str:
        """Generate recommendations section."""
        if not analysis or not analysis.get("recommendations"):
            return ""
        
        rec_html = ['<div class="recommendations">', '<div class="metric-title">Recommendations</div>']
        
        for rec in analysis["recommendations"]:
            rec_html.append(f"""
            <div class="recommendation-item">
                {rec}
            </div>
            """)
        
        rec_html.append('</div>')
        return ''.join(rec_html)
    
    def _generate_trends_section(self, historical_data: List[Dict[str, Any]]) -> str:
        """Generate trends section (simplified)."""
        if not historical_data:
            return ""
        
        # Simple trend analysis
        recent_coverage = []
        recent_success_rates = []
        
        for data in historical_data[-10:]:  # Last 10 data points
            if "coverage" in data:
                recent_coverage.append(data["coverage"].get("line_coverage_percent", 0))
            if "test_results" in data:
                recent_success_rates.append(data["test_results"].get("success_rate", 0) * 100)
        
        trend_html = ['<div class="metric-card" style="grid-column: 1 / -1;">', '<div class="metric-title">Trends</div>']
        
        if recent_coverage:
            avg_coverage = sum(recent_coverage) / len(recent_coverage)
            trend_html.append(f"<p>Average Coverage (last 10 runs): {avg_coverage:.1f}%</p>")
        
        if recent_success_rates:
            avg_success = sum(recent_success_rates) / len(recent_success_rates)
            trend_html.append(f"<p>Average Success Rate (last 10 runs): {avg_success:.1f}%</p>")
        
        trend_html.append(f"<p>Historical Data Points: {len(historical_data)}</p>")
        trend_html.append('</div>')
        
        return ''.join(trend_html)
    
    def save_dashboard(self, output_file: Path = None) -> Path:
        """Save dashboard HTML to file."""
        if output_file is None:
            output_file = self.project_root / "test_dashboard.html"
        
        html_content = self.generate_html_dashboard()
        
        with open(output_file, 'w') as f:
            f.write(html_content)
        
        return output_file


def main():
    """Main entry point for dashboard generation."""
    import argparse
    import sys
    import webbrowser
    
    parser = argparse.ArgumentParser(description="Test Quality Dashboard")
    parser.add_argument("--output", help="Output HTML file path")
    parser.add_argument("--open", action="store_true", help="Open dashboard in browser")
    parser.add_argument("--serve", action="store_true", help="Serve dashboard on local HTTP server")
    parser.add_argument("--port", type=int, default=8080, help="Port for HTTP server")
    parser.add_argument("--host", default="localhost", help="Host for HTTP server")
    
    args = parser.parse_args()
    
    # Initialize dashboard
    dashboard = TestDashboard()
    
    # Generate and save dashboard
    output_file = Path(args.output) if args.output else None
    dashboard_file = dashboard.save_dashboard(output_file)
    
    print(f"Dashboard generated: {dashboard_file}")
    
    if args.serve:
        # Serve dashboard on HTTP server
        import http.server
        import socketserver
        import threading
        
        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(dashboard_file.parent), **kwargs)
        
        with socketserver.TCPServer((args.host, args.port), Handler) as httpd:
            url = f"http://{args.host}:{args.port}/{dashboard_file.name}"
            print(f"Serving dashboard at: {url}")
            
            if args.open:
                webbrowser.open(url)
            
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\\nShutting down server...")
    
    elif args.open:
        # Open dashboard in browser
        webbrowser.open(f"file://{dashboard_file.absolute()}")


if __name__ == "__main__":
    main()