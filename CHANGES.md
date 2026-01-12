# Changes Summary - Background Command Execution Fix

## Problem Statement

Users reported that long-running commands would stop executing when they closed the browser page, and production logs showed hundreds of `pylibmc.TooBig` and `RecursionError` exceptions.

## Root Causes Identified

1. **Threading issue**: Commands ran in regular threads tied to Django worker lifecycle
2. **Cache size errors**: Output exceeded memcached 1MB limit, causing cascade failures
3. **Infinite recursion**: Error handlers used `print()` which called `write()` recursively
4. **Locmem cache incompatibility**: Default cache doesn't work across processes

## Solutions Implemented

### 1. Process-Based Background Execution
**File**: `command_runner/views.py` (lines 191-296)

- Replaced `threading.Thread` with `multiprocessing.Process`
- Commands run in isolated OS processes that survive page closes and Django restarts
- Uses 'spawn' context for cross-platform compatibility
- Non-daemon processes ensure completion even if parent process exits

### 2. Fixed Cache Errors
**File**: `command_runner/views.py` (lines 76-105)

- **Batched updates**: Cache updates every 5KB instead of every write
- **Better size limits**: Reserved 10KB overhead (reduced to ~1014KB max)
- **Graceful degradation**: Disables cache updates on first failure
- **Removed print() in error handlers**: Prevents infinite recursion

### 3. Added Memcached Support
**Files**:
- `docker-compose.yml`: Added memcached service
- `requirements.txt`: Added pymemcache==4.0.0
- `test_project/settings.py`: Configured PyMemcacheCache

Memcached provides process-safe cache that works across spawned processes.

### 4. Comprehensive Test Suite
**File**: `command_runner/tests.py`

Created 11 tests covering:
- Background process execution
- Cache size handling
- Fault tolerance
- Process isolation
- Argument passing
- Security (staff-only access)

**All tests pass** ✅

## Migration Guide

### For Existing Installations

1. **Update requirements.txt**:
   ```
   pymemcache>=4.0.0
   ```

2. **Install and configure memcached**:
   ```bash
   # Ubuntu/Debian
   sudo apt-get install memcached
   sudo systemctl start memcached

   # macOS
   brew install memcached
   brew services start memcached
   ```

3. **Update Django settings.py**:
   ```python
   CACHES = {
       'default': {
           'BACKEND': 'django.core.cache.backends.memcached.PyMemcacheCache',
           'LOCATION': '127.0.0.1:11211',
       }
   }
   ```

4. **For Docker deployments**: Use the updated `docker-compose.yml` which includes memcached service

5. **Restart Django** to pick up new code and configuration

### Testing the Fix

```bash
# Run automated tests
python manage.py test command_runner

# Manual test
python test_background_execution.py

# Or test in browser:
# 1. Start a long-running command
# 2. Close the browser tab immediately
# 3. Wait a few minutes
# 4. Reopen and check /command-runner/status/<command_id>/
# 5. Command should show as completed successfully
```

## Benefits

✅ Commands complete successfully even if users close the browser
✅ No more `pylibmc.TooBig` errors
✅ No more recursion errors
✅ Commands survive Django worker restarts
✅ Better performance with batched cache updates
✅ Graceful error handling without crashes

## Breaking Changes

⚠️ **Requires memcached or redis** - The default locmem cache no longer works. You must configure a process-safe cache backend.

## Files Changed

- `command_runner/views.py` - Core multiprocessing and cache improvements
- `command_runner/tests.py` - Comprehensive test suite
- `docker-compose.yml` - Added memcached service
- `requirements.txt` - Added pymemcache
- `test_project/settings.py` - Cache configuration
- `CLAUDE.md` - Updated documentation
- `test_background_execution.py` - Manual testing script (new)
- `RUN_TESTS.md` - Testing instructions (new)

## Performance Impact

- Slightly higher memory usage (separate processes vs threads)
- Reduced cache operations (batched updates)
- Overall: Net positive, especially for long-running commands

## Security Considerations

- No changes to authentication (still requires staff access)
- Process isolation provides additional security boundary
- Cache data still has 1-hour timeout

## Support

If you encounter issues after upgrading:

1. Ensure memcached is running: `telnet localhost 11211`
2. Check Django can connect: `python manage.py shell` then `from django.core.cache import cache; cache.set('test', 'ok'); cache.get('test')`
3. Verify DJANGO_SETTINGS_MODULE is set in environment
4. Check logs for any Python multiprocessing errors
5. On Windows, multiprocessing behavior may differ - ensure 'spawn' context works
