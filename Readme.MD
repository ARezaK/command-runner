# CommandRunner

Run Django management commands from a web interface with real-time output streaming. Commands run in background processes and continue even if the user closes their browser.

## Features

- ✅ Run any Django management command from the web UI
- ✅ Real-time output streaming
- ✅ Commands continue in background (survive browser close)
- ✅ Multiple concurrent commands supported
- ✅ Staff-only access for security
- ✅ Automatic output filtering (SQL queries, progress bars)

## Requirements

- Django 4.2+
- Python 3.10+
- **A process-safe cache backend** (memcached, redis, database, or file-based)
  - ⚠️ Django's default `locmem` cache **will not work**

## Installation

### 1. Install Package

Add to `requirements.txt`:
```
CommandRunner@ git+https://github.com/ARezaK/command-runner.git
pymemcache>=4.0.0  # or redis>=4.0.0 for Redis
```

Then install:
```bash
pip install -r requirements.txt
```

### 2. Configure Django

Add to `INSTALLED_APPS` in `settings.py`:
```python
INSTALLED_APPS = [
    ...
    'command_runner',
    ...
]
```

Add to `urls.py`:
```python
from django.urls import path, include

urlpatterns = [
    ...
    path('command-runner/', include('command_runner.urls')),
    ...
]
```

### 3. Configure Cache Backend (REQUIRED)

Choose one option:

**Option A: Memcached (Recommended)**
```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.memcached.PyMemcacheCache',
        'LOCATION': '127.0.0.1:11211',
    }
}
```

**Option B: Redis**
```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379',
    }
}
```

**Option C: Database Cache** (no external service needed)
```bash
python manage.py createcachetable
```
```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'command_runner_cache',
    }
}
```

**Option D: File Cache** (development only)
```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': '/var/tmp/django_cache',
    }
}
```

See `CACHE_SETUP_GUIDE.md` for detailed setup instructions.

### 4. Copy Templates

Copy the `templates/` folder from this repository to your project's main app folder.

### 5. Restart Django

```bash
python manage.py runserver
```

## Usage

1. Navigate to `http://your-domain/command-runner/`
2. Login with a staff account
3. Select a command from the dropdown
4. Enter any arguments (optional)
5. Click "Run Command"
6. View real-time output

**Note:** You can safely close the browser - commands will continue running in the background!

## Testing

Run the test suite:
```bash
python manage.py test command_runner
```

Test production scenarios:
```bash
python test_production_scenarios.py
```

## Docker Setup

```bash
docker-compose up --build
```

The docker setup includes memcached automatically.

## Troubleshooting

**Commands not completing when browser closes?**
- Check your cache configuration - you may be using `locmem` cache
- Run: `python test_background_execution.py` to verify

**"Connection refused" errors?**
- If using memcached/redis, ensure the service is running
- Check: `telnet localhost 11211` (memcached) or `redis-cli ping` (redis)

**No output appearing?**
- Check Django logs for errors
- Verify cache backend is configured correctly
- Ensure you're logged in as staff user

## Documentation

- `CLAUDE.md` - Architecture and development guide
- `CACHE_SETUP_GUIDE.md` - Detailed cache configuration
- `CHANGES.md` - Recent improvements and migration guide
- `TEST_RESULTS.md` - Test coverage and results

## Security

- All views require staff authentication (`@staff_member_required`)
- CSRF protection enabled
- Commands run with Django app permissions
- No command injection vulnerabilities

## License

MIT
