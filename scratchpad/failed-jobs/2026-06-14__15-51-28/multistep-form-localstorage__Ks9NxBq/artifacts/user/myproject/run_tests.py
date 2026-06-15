"""Simple test runner for the wizard State."""

import sys
import test_wizard

def main():
    test_funcs = [
        test_wizard.test_initial_state,
        test_wizard.test_step1_validation_empty,
        test_wizard.test_step1_validation_invalid_email,
        test_wizard.test_step1_validation_success,
        test_wizard.test_step2_validation_empty,
        test_wizard.test_step2_validation_success,
        test_wizard.test_step3_validation_empty,
        test_wizard.test_step3_validation_mismatch,
        test_wizard.test_step3_validation_success_and_clear,
        test_wizard.test_prev_step,
    ]
    
    passed = 0
    failed = 0
    for func in test_funcs:
        try:
            func()
            print(f"PASS: {func.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {func.__name__} - {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR: {func.__name__} - {type(e).__name__}: {e}")
            failed += 1
            
    print(f"\nResults: {passed} passed, {failed} failed")
    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
