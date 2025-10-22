# Test Quality Monitoring Guide

This guide provides comprehensive information about test quality monitoring, metrics collection, and performance optimization for the Hywel Dda IPAR Document Miner project.

## Overview

The test suite includes comprehensive quality monitoring tools that track:
- **Coverage metrics** - Line and branch coverage across all code
- **Performance metrics** - Test execution times and optimization opportunities  
- **Reliability metrics** - Test success rates and flaky test detection
- **Failure analysis** - Automated debugging assistance and fix suggestions

## Quick Start

### Running Quality Checks

```bash
# Run all tests with comprehensive metrics
make test-metrics

# Generate coverage report
make test-coverage

# Analyze test performance
make test-performance

# Open interactive dashboard
make test-dashboard

# Analyze any test failures
make test-analyze-failures
```

### Daily Workflow

1. **Before committing code**: Run `make test-coverage` to ensure coverage targets are met
2. **After test failures**: Run `make test-analyze-failures` for debugging assistance
3. **Weekly review**: Check `make test-dashboard` for trends and quality metrics
4. **Performance optimization**: Use `make test-performance` to identify slow tests

## Quality Thresholds

### Coverage Requirements
- **Total Coverage**: ≥80% (line coverage)
- **Service Layer**: ≥90% (business logic)
- **Critical Paths**: 100% (core workflows)
- **Branch Coverage**: ≥75% (decision points)

### Performance Standards
- **Unit Tests**: ≤100ms per test
- **Integration Tests**: ≤1s per test  
- **System Tests**: ≤10s per test
- **Total Suite**: ≤5 minutes

### Reliability Standards
- **Success Rate**: ≥99%
- **Flaky Test Rate**: ≤1%
- **Test Isolation**: 100% (no interdependencies)

## Test Organization

### Test Categories

#### Unit Tests (`tests/unit/`)
- **Purpose**: Test individual components in isolation
- **Scope**: Single functions/methods with mocked dependencies
- **Coverage Target**: >90%
- **Performance Target**: <100ms per test

#### Integration Tests (`tests/integration/`)
- **Purpose**: Test component interactions
- **Scope**: Multiple services working together
- **Coverage Target**: >85%
- **Performance Target**: <1s per test

#### System Tests (`tests/system/`)
- **Purpose**: End-to-end workflow validation
- **Scope**: Complete user scenarios
- **Coverage Target**: >80%
- **Performance Target**: <10s per test

### Test Structure Standards

```python
class TestServiceName:
    """Test class following standard structure."""
    
    def test_method_success_case(self, fixtures):
        """Test successful execution."""
        # Arrange
        # Act  
        # Assert
        
    def test_method_error_handling(self, fixtures):
        """Test error conditions."""
        # Arrange
        # Act & Assert (with pytest.raises)
        
    def test_method_edge_cases(self, fixtures):
        """Test boundary conditions."""
        # Arrange
        # Act
        # Assert
```

## Monitoring Tools

### 1. Test Metrics Collector (`tests/test_metrics.py`)

Comprehensive metrics collection and analysis:

```bash
# Collect metrics with report generation
python tests/test_metrics.py --generate-report --check-thresholds

# Output directory customization
python tests/test_metrics.py --output-dir ./custom/path
```

**Features:**
- Coverage analysis (line, branch, file-level)
- Performance profiling (execution times, slowest tests)
- Test result analysis (pass/fail rates, error categorization)
- Quality threshold validation
- Historical trend tracking

### 2. Failure Analysis (`tests/failure_analysis.py`)

Automated failure debugging and pattern detection:

```bash
# Analyze current failures
python tests/failure_analysis.py --analyze-failures --suggest-fixes

# Track flaky tests
python tests/failure_analysis.py --track-flaky

# Generate debugging guide for specific test
python tests/failure_analysis.py --debug-test "test_name"
```

**Features:**
- Pattern recognition (import errors, assertion failures, timeouts)
- Fix suggestions based on error types
- Flaky test identification and tracking
- Historical failure analysis
- Debugging guide generation

### 3. Test Dashboard (`tests/test_dashboard.py`)

Interactive web dashboard for real-time monitoring:

```bash
# Generate static dashboard
python tests/test_dashboard.py --output dashboard.html --open

# Serve live dashboard
python tests/test_dashboard.py --serve --port 8080 --open
```

**Features:**
- Real-time metrics visualization
- Coverage and performance trends
- Issue tracking and recommendations
- Historical data analysis
- Auto-refresh capabilities

## Performance Optimization

### Identifying Slow Tests

```bash
# Show slowest tests
pytest tests/ --durations=10 --durations-min=0.01

# Performance-focused configuration
pytest tests/ -c tests/pytest_performance.ini
```

### Optimization Strategies

#### Unit Test Optimization
1. **Minimize setup complexity**
   - Use lightweight fixtures
   - Avoid expensive object creation
   - Mock external dependencies

2. **Optimize assertions**
   - Use specific assertions (`assert x == y` vs `assert x`)
   - Avoid complex computations in assertions

3. **Reduce I/O operations**
   - Mock file operations
   - Use in-memory data structures
   - Avoid network calls

#### Integration Test Optimization
1. **Selective mocking**
   - Mock only external services
   - Use real implementations for core logic
   - Share expensive setup across tests

2. **Test data management**
   - Use factories for test data generation
   - Implement efficient cleanup procedures
   - Reuse compatible test data

#### System Test Optimization
1. **Workflow efficiency**
   - Test multiple scenarios in single workflow
   - Use transaction rollbacks for cleanup
   - Implement parallel execution where safe

## Coverage Analysis

### Understanding Coverage Reports

#### HTML Report (`htmlcov/index.html`)
- Interactive file-by-file coverage analysis
- Line-by-line coverage highlighting
- Branch coverage visualization
- Missing coverage identification

#### XML Report (`coverage.xml`)
- Machine-readable format for CI/CD
- Detailed metrics for automated analysis
- Integration with external tools

#### Terminal Report
- Quick overview during development
- Missing line identification
- Summary statistics

### Improving Coverage

#### Systematic Approach
1. **Identify uncovered code**
   ```bash
   pytest tests/ --cov=app --cov-report=term-missing
   ```

2. **Prioritize by importance**
   - Critical business logic first
   - Error handling paths
   - Edge cases and boundary conditions

3. **Add targeted tests**
   - Focus on specific uncovered lines
   - Test both success and failure paths
   - Include edge cases

#### Coverage Exclusions
Use coverage pragmas for legitimate exclusions:

```python
def debug_only_function():  # pragma: no cover
    """Function only used in debug mode."""
    pass

if TYPE_CHECKING:  # pragma: no cover
    from typing import Optional
```

## Failure Debugging

### Common Failure Patterns

#### Import Errors
```
ImportError: No module named 'app.services.missing_service'
```
**Solutions:**
- Check module path spelling
- Verify `__init__.py` files exist
- Check for circular imports
- Ensure module is in Python path

#### Assertion Errors
```
AssertionError: assert 42 == 43
```
**Solutions:**
- Review expected vs actual values
- Check test data accuracy
- Verify implementation logic
- Consider floating-point precision

#### Mock Configuration Errors
```
AttributeError: Mock object has no attribute 'method_name'
```
**Solutions:**
- Verify mock target path
- Check mock setup and configuration
- Review mock call expectations
- Ensure proper mock cleanup

### Debugging Workflow

1. **Reproduce locally**
   ```bash
   pytest path/to/failing_test.py::TestClass::test_method -v
   ```

2. **Increase verbosity**
   ```bash
   pytest path/to/failing_test.py::TestClass::test_method -vvv -s
   ```

3. **Use debugger**
   ```bash
   pytest path/to/failing_test.py::TestClass::test_method --pdb
   ```

4. **Check test isolation**
   ```bash
   pytest path/to/failing_test.py::TestClass::test_method --lf
   ```

## Flaky Test Management

### Identification
Flaky tests are automatically tracked based on:
- Intermittent failures (not always failing)
- Multiple different failure messages
- Failure rate between 1-30%

### Resolution Strategies

#### Common Causes
1. **Race conditions**
   - Add proper synchronization
   - Use deterministic timing
   - Implement retry mechanisms

2. **External dependencies**
   - Mock external services
   - Use test doubles
   - Implement circuit breakers

3. **Test isolation issues**
   - Ensure proper cleanup
   - Use fresh test data
   - Avoid shared state

4. **Timing dependencies**
   - Remove sleep statements
   - Use event-driven waiting
   - Mock time-dependent operations

## Continuous Integration

### CI/CD Integration

#### GitHub Actions Example
```yaml
name: Test Quality Check
on: [push, pull_request]

jobs:
  test-quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.11
      - name: Install dependencies
        run: make install
      - name: Run quality checks
        run: make test-metrics
      - name: Upload coverage
        uses: codecov/codecov-action@v1
        with:
          file: ./coverage.xml
```

#### Quality Gates
- **Coverage threshold**: Fail if coverage drops below 80%
- **Performance regression**: Fail if test suite time increases >20%
- **Reliability check**: Fail if success rate drops below 99%

### Automated Reporting

#### Daily Reports
- Coverage trend analysis
- Performance regression detection
- Flaky test identification
- Quality metric summaries

#### Weekly Reviews
- Test suite health assessment
- Technical debt identification
- Optimization recommendations
- Quality improvement planning

## Best Practices

### Test Writing Guidelines

1. **Follow AAA Pattern**
   ```python
   def test_example():
       # Arrange - Set up test data and conditions
       user = User(name="Test User")
       
       # Act - Execute the code being tested
       result = user.get_display_name()
       
       # Assert - Verify the expected outcome
       assert result == "Test User"
   ```

2. **Use descriptive test names**
   ```python
   # Good
   def test_user_login_with_valid_credentials_returns_success()
   
   # Bad
   def test_login()
   ```

3. **Test one thing at a time**
   ```python
   # Good - focused test
   def test_calculate_tax_with_standard_rate():
       assert calculate_tax(100, 0.1) == 10
   
   # Bad - testing multiple scenarios
   def test_calculate_tax():
       assert calculate_tax(100, 0.1) == 10
       assert calculate_tax(200, 0.2) == 40
       assert calculate_tax(0, 0.1) == 0
   ```

### Mock Usage Guidelines

1. **Mock external dependencies only**
   ```python
   # Good - mock external service
   @patch('app.services.external_api.requests.post')
   def test_api_call(mock_post):
       mock_post.return_value.json.return_value = {"status": "success"}
   
   # Bad - mocking internal logic
   @patch('app.services.user_service.User.validate')
   def test_user_creation(mock_validate):
       pass  # This should test real validation logic
   ```

2. **Use appropriate mock types**
   ```python
   # For simple return values
   mock_service.method.return_value = "result"
   
   # For exceptions
   mock_service.method.side_effect = ValueError("Error message")
   
   # For multiple calls
   mock_service.method.side_effect = ["first", "second", "third"]
   ```

### Fixture Management

1. **Use appropriate scopes**
   ```python
   @pytest.fixture(scope="session")  # Expensive setup, shared across all tests
   def database_connection():
       pass
   
   @pytest.fixture(scope="function")  # Fresh data for each test
   def user_data():
       pass
   ```

2. **Implement proper cleanup**
   ```python
   @pytest.fixture
   def temp_file():
       file_path = create_temp_file()
       yield file_path
       os.remove(file_path)  # Cleanup
   ```

## Troubleshooting

### Common Issues

#### Coverage Not Updating
- Check coverage configuration in `pytest.ini`
- Verify source paths are correct
- Ensure tests are actually running
- Check for coverage exclusions

#### Tests Running Slowly
- Profile test execution with `--durations`
- Identify expensive fixtures
- Review mock configurations
- Check for unnecessary I/O operations

#### Flaky Test Detection
- Ensure sufficient test history
- Check test isolation
- Review timing dependencies
- Verify mock configurations

### Getting Help

1. **Check test logs**
   ```bash
   pytest tests/ -v --tb=long
   ```

2. **Use failure analysis tool**
   ```bash
   python tests/failure_analysis.py --analyze-failures
   ```

3. **Review quality dashboard**
   ```bash
   make test-dashboard
   ```

4. **Consult team documentation**
   - Review recent changes in git history
   - Check team communication channels
   - Consult with test maintainers

## Maintenance

### Regular Tasks

#### Daily
- [ ] Run test suite before committing
- [ ] Check coverage for new code
- [ ] Review any test failures

#### Weekly  
- [ ] Review test performance metrics
- [ ] Check for flaky tests
- [ ] Update test documentation

#### Monthly
- [ ] Analyze coverage trends
- [ ] Review and update quality thresholds
- [ ] Optimize slow tests
- [ ] Update testing tools and dependencies

### Quality Improvement

#### Continuous Improvement Process
1. **Measure** - Collect quality metrics
2. **Analyze** - Identify improvement opportunities  
3. **Plan** - Prioritize quality improvements
4. **Implement** - Execute improvement plans
5. **Verify** - Validate improvements with metrics

#### Success Metrics
- Coverage trend (should increase over time)
- Test execution time (should remain stable or decrease)
- Flaky test count (should decrease over time)
- Developer satisfaction with test suite

---

For questions or suggestions about test quality monitoring, please consult the development team or update this documentation with new findings and best practices.