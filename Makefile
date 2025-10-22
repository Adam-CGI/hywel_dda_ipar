.PHONY: help install run test upload clean test-metrics test-coverage test-performance test-dashboard test-analyze-failures

help:
	@echo "Hywel Dda IPAR Document Miner - Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  install              - Install Python dependencies"
	@echo "  run                  - Run Flask development server"
	@echo "  test                 - Run tests"
	@echo "  upload               - Upload a document (requires FILE=path/to/file.pdf)"
	@echo "  clean                - Clean Python cache files"
	@echo ""
	@echo "Test Quality Monitoring:"
	@echo "  test-metrics         - Collect comprehensive test metrics"
	@echo "  test-coverage        - Run tests with detailed coverage analysis"
	@echo "  test-performance     - Run performance-focused test analysis"
	@echo "  test-dashboard       - Generate and open test quality dashboard"
	@echo "  test-analyze-failures - Analyze test failures and suggest fixes"

install:
	pip install -r requirements.txt

run:
	python app.py

test:
	pytest tests/ -v

upload:
ifndef FILE
	@echo "Error: FILE not specified. Usage: make upload FILE=path/to/file.pdf"
	@exit 1
endif
	curl -X POST http://localhost:8000/api/documents/upload \
		-F "file=@$(FILE)" \
		-H "Accept: application/json"

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +

# Test Quality Monitoring Targets
test-metrics:
	@echo "Collecting comprehensive test metrics..."
	python tests/test_metrics.py --generate-report --check-thresholds

test-coverage:
	@echo "Running detailed coverage analysis..."
	pytest tests/ -v --cov=app --cov-report=html --cov-report=xml --cov-report=term-missing --cov-fail-under=80

test-performance:
	@echo "Running performance-focused test analysis..."
	pytest tests/ -v --durations=10 --durations-min=0.01 -c tests/pytest_performance.ini

test-dashboard:
	@echo "Generating test quality dashboard..."
	python tests/test_dashboard.py --output test_dashboard.html --open
	@echo "Dashboard available at: test_dashboard.html"

test-analyze-failures:
	@echo "Analyzing test failures..."
	python tests/failure_analysis.py --analyze-failures --track-flaky --suggest-fixes
