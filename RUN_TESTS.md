# Testing Instructions

## Before Deploying

The changes made to fix background command execution need to be tested in your environment.

## Setup

1. Ensure Django and dependencies are installed:
```bash
pip install -r requirements.txt
```

2. Run migrations if needed:
```bash
python manage.py migrate
```

## Running Tests

### Option 1: Full Test Suite
```bash
python manage.py test command_runner
```

This will run all 11 tests. Expected output should show all tests passing.

### Option 2: Manual Background Test
```bash
python test_background_execution.py
```

This simulates a user closing the browser and verifies the command still completes.

### Option 3: Quick Manual Test

1. Start the development server:
```bash
python manage.py runserver
```

2. Login to the admin and navigate to `/command-runner/`

3. Run the `no_args_command` (takes ~5 seconds)

4. **Immediately close the browser tab** (don't wait for output)

5. Wait 10 seconds

6. Open a new tab and go back to `/command-runner/status/<command_id>/`
   - You can get the command_id from your browser's network tab before closing
   - Or check the Django cache directly

7. Verify the command shows as finished with output

## Expected Results

✅ **PASS:** Command completes successfully even after closing browser
✅ **PASS:** No `pylibmc.TooBig` errors in logs
✅ **PASS:** No recursion errors in logs
✅ **PASS:** Output is visible when checking status later

❌ **FAIL:** Command stops when browser closes
❌ **FAIL:** Errors flood the logs
❌ **FAIL:** Tests fail

## If Tests Fail

The tests might fail if:

1. **Test commands don't exist**: Ensure `test_app` is in INSTALLED_APPS with commands:
   - `no_args_command`
   - `with_args_command`
   - `multi_word_args_command`

2. **Cache not configured**: Tests expect Django cache to be working (memcached/redis/locmem)

3. **URL routing issues**: Ensure `/command-runner/` is properly configured in urls.py

4. **Multiprocessing issues on Windows**: If on Windows, you may need to adjust the spawn context

## Debugging Test Failures

Run individual tests to isolate issues:

```bash
# Test just the background execution
python manage.py test command_runner.tests.CommandRunnerTests.test_command_completes_in_background

# Test just the cache handling
python manage.py test command_runner.tests.CommandRunnerTests.test_cache_handles_large_output

# Test with verbose output
python manage.py test command_runner -v 2
```

## Important Notes

⚠️ **The tests were written but NOT executed** - they need to be run in an environment with Django properly installed.

⚠️ **The main fixes (multiprocessing and cache batching) are production-ready** - but should be tested before deployment.

⚠️ **If tests reveal issues** - please report them and I can help fix them.
