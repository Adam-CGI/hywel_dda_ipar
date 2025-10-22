# Test Quality Report
Generated: 2025-10-22 13:42:21

## Overall Status: FAIL

## Coverage Summary
- **Total Coverage**: 76.1%
- **Branch Coverage**: 85.0%
- **Statements**: 969/1273
- **Branches**: 91/107

## Test Execution Summary
- **Total Tests**: 0
- **Passed**: 0
- **Failed**: 0
- **Errors**: 0
- **Skipped**: 0
- **Success Rate**: 0.0%
- **Execution Time**: 0.00s

## Performance Summary
### Integration Tests
- **Count**: 7
- **Average Time**: 0.637s
- **Slowest**: 0.940s
- **Total Time**: 4.460s

## Issues Found

- **HIGH**: Total coverage 76.1% below threshold 80.0%
- **MEDIUM**: Service layer coverage 69.2% below threshold 90.0%
- **HIGH**: Test success rate 0.0% below threshold 99.0%

## Recommendations

- Add unit tests for uncovered service methods
- Focus on testing error handling and edge cases
- Consider adding integration tests for multi-service workflows
- Review and test critical business logic paths
- Investigate and fix failing tests immediately
- Review test isolation and cleanup procedures
- Add retry mechanisms for flaky external dependencies
- Improve test data management and consistency

## Quality Thresholds
### Coverage
- Total Coverage: >=80.0%
- Service Layer: >=90.0%
- Critical Paths: >=100.0%

### Performance
- Unit Test Max Time: <=0.1s
- Integration Test Max Time: <=1.0s
- System Test Max Time: <=10.0s
- Total Suite Max Time: <=300.0s

### Reliability
- Max Flaky Rate: <=1.0%
- Min Success Rate: >=99.0%
