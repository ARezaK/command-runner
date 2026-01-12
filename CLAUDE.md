# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CommandRunner is a Django app that provides a web interface for running Django management commands. It allows staff users to execute management commands through a browser with real-time output streaming.

## Architecture

### Core Components

**Views (command_runner/views.py)**
- `command_list`: Main view that displays available commands (filters out default Django commands)
- `start_command`: Starts a management command in a background thread
- `command_status`: Polls for command execution status and output

**Background Execution Pattern**
- Commands run in separate processes (using `multiprocessing`) to ensure they continue even if the user closes the page
- Process-based execution (not threads) ensures commands survive Django worker restarts
- Uses 'spawn' context for better cross-platform compatibility and process isolation
- Output is captured via `FilteredStringIO` which extends `StringIO`
- Real-time output is cached using Django's cache framework with a 1-hour timeout
- Frontend polls `/command-runner/status/<command_id>/` every second for updates

**Output Filtering (FilteredStringIO class in views.py:20-125)**
- Filters SQL queries and progress indicators from command output
- Uses regex patterns to detect and skip SQL statements and download progress
- Batched cache updates (every 1KB OR every 2 seconds) to reduce memcached load
- Enforces ~1MB max cache size (minus 10KB overhead) to prevent memcached TooBig errors
- Graceful failure: If cache write fails, disables future updates (sets interval to infinity)
- Prevents infinite recursion by not using print() in error handling

**Cache Strategy**
- Commands are identified by UUID
- Cache key format: `command_runner:{command_id}`
- Stored data: `{'output': str, 'error': str, 'finished': bool}`
- Automatic truncation if output exceeds MAX_CACHE_SIZE (1MB)
- **Requires process-safe cache backend** - locmem cache doesn't work across processes
  - **Production:** memcached or redis (recommended)
  - **Alternative:** database cache or file-based cache (slower but works)

### URL Structure

```
/command-runner/              → command_list (GET: display, POST: sync execution)
/command-runner/start/        → start_command (POST: async execution)
/command-runner/status/<id>/  → command_status (GET: poll status)
```

### Template Integration

The app uses Django admin templates as base (`admin/base_site.html`) and requires staff authentication (`@staff_member_required` decorator).

## Development Commands

**Run test server:**
```bash
python manage.py runserver
```

**Run migrations:**
```bash
python manage.py migrate
```

**Run all tests:**
```bash
python manage.py test command_runner
```

**Run a single test:**
```bash
python manage.py test command_runner.tests.CommandRunnerTests.test_command_completes_in_background
```

**Run manual background execution test:**
```bash
python test_background_execution.py
```
This test verifies that commands continue running even when the user closes the browser.

**Create superuser (custom auto command):**
```bash
python manage.py create_superuser_auto
```

## Docker Setup

**Build and run:**
```bash
docker-compose up --build
```

The docker-compose setup includes:
- `web`: Django application server
- `memcached`: Required for cross-process cache communication

The docker-entrypoint.sh script automatically:
1. Applies migrations
2. Creates a superuser
3. Starts the Django development server

## Testing

The repository includes a `test_app` with example management commands:
- `no_args_command`: Simple command that sleeps and prints messages
- `with_args_command`: Command that accepts positional args and optional flags
- `multi_word_args_command`: Command demonstrating multi-word arguments

## Key Implementation Details

**Command Discovery**
- Uses `django.core.management.get_commands()` to discover available commands
- Automatically filters out default Django commands (those from 'django' apps)
- Caches command help text indefinitely

**Security**
- All views require staff member authentication
- CSRF protection enabled with `@ensure_csrf_cookie`
- SQL query output is filtered from display

**Output Handling**
- stdout and stderr are both captured through FilteredStringIO
- System stdout/stderr are temporarily replaced during command execution
- Logging level for django.db.backends is set to WARNING to reduce noise

## Installation as Package

To install CommandRunner in another Django project:

1. Add to requirements.txt:
   ```
   CommandRunner@ git+https://github.com/ARezaK/command-runner.git
   pymemcache>=4.0.0
   ```

2. Add to INSTALLED_APPS:
   ```python
   INSTALLED_APPS = [
       ...
       'command_runner',
       ...
   ]
   ```

3. Configure cache backend in settings.py (choose one):

   **Option A: Memcached (Recommended for Production)**
   ```python
   # Install: apt-get install memcached (Ubuntu) or brew install memcached (Mac)
   # Add to requirements.txt: pymemcache>=4.0.0
   CACHES = {
       'default': {
           'BACKEND': 'django.core.cache.backends.memcached.PyMemcacheCache',
           'LOCATION': '127.0.0.1:11211',
       }
   }
   ```

   **Option B: Redis (If You Already Have Redis)**
   ```python
   # Install: apt-get install redis (Ubuntu) or brew install redis (Mac)
   # Add to requirements.txt: redis>=4.0.0
   CACHES = {
       'default': {
           'BACKEND': 'django.core.cache.backends.redis.RedisCache',
           'LOCATION': 'redis://127.0.0.1:6379',
       }
   }
   ```

   **Option C: Database Cache (No External Service)**
   ```python
   # Run: python manage.py createcachetable
   CACHES = {
       'default': {
           'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
           'LOCATION': 'command_runner_cache',
       }
   }
   ```

   **Option D: File-Based Cache (Development Only)**
   ```python
   # Slowest but simplest for local development
   CACHES = {
       'default': {
           'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
           'LOCATION': '/var/tmp/django_cache',
       }
   }
   ```

   **Note:** Django's default `locmem` cache won't work because it doesn't share data across processes.

4. Add to urls.py:
   ```python
   path('command-runner/', include('command_runner.urls')),
   ```

5. Copy the templates folder to your main app folder
