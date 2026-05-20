
"""
Regression tests for regression-manager -- multi-run comparison.
"""
import sys, os, json, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_two_runs_compare():
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from regression_manager import RegressionManager
    rm = RegressionManager()
    run_a = rm.create_run(module="test", total=10, passed=10, failed=0)
    run_b = rm.create_run(module="test", total=10, passed=7, failed=3)
    result = rm.compare_runs(run_a, run_b)
    assert result["regression_fails"] == 3

def test_regression_db():
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        from regression_manager import RegressionManager
        rm = RegressionManager(db_path="test_regression.json")
        rm.create_run(module="test", total=5, passed=5, failed=0)
        rm2 = RegressionManager(db_path="test_regression.json")
        assert len(rm2.history) >= 1
