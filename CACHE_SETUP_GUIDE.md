# Cache Backend Setup Guide

## Why Do I Need This?

The background command execution feature uses **multiprocessing** (separate OS processes) instead of threads. This means each process has its own memory space and can't share Django's default `locmem` cache.

You need a cache backend that works **across processes**.

## Quick Decision Guide

**Already have memcached?** → Use memcached (Option A)
**Already have redis?** → Use redis (Option B)
**Don't want external services?** → Use database cache (Option C)
**Just testing locally?** → Use file cache (Option D)

---

## Option A: Memcached (Recommended for Production)

**Best for:** Production deployments, high performance needed

### Install Memcached
```bash
# Ubuntu/Debian
sudo apt-get install memcached
sudo systemctl start memcached
sudo systemctl enable memcached

# macOS
brew install memcached
brew services start memcached

# Docker
# Already included in docker-compose.yml
```

### Install Python Client
```bash
pip install pymemcache
```

### Configure Django
```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.memcached.PyMemcacheCache',
        'LOCATION': '127.0.0.1:11211',
    }
}
```

### Verify It Works
```bash
python manage.py shell
```
```python
from django.core.cache import cache
cache.set('test', 'works!')
print(cache.get('test'))  # Should print: works!
```

**Pros:**
- ✅ Very fast
- ✅ Designed for this use case
- ✅ Production-grade
- ✅ Low memory usage

**Cons:**
- ❌ Requires external service
- ❌ Data lost on restart (but that's fine for command output)

---

## Option B: Redis

**Best for:** Projects already using Redis

### Install Redis
```bash
# Ubuntu/Debian
sudo apt-get install redis
sudo systemctl start redis
sudo systemctl enable redis

# macOS
brew install redis
brew services start redis
```

### Install Python Client
```bash
pip install redis
```

### Configure Django
```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379',
    }
}
```

**Pros:**
- ✅ Fast
- ✅ More features than memcached
- ✅ May already be in your stack
- ✅ Persistent (optional)

**Cons:**
- ❌ Requires external service
- ❌ Slightly heavier than memcached

---

## Option C: Database Cache

**Best for:** Simplicity, no external services

### Setup
```bash
python manage.py createcachetable
```

### Configure Django
```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'command_runner_cache',
    }
}
```

**Pros:**
- ✅ No external service needed
- ✅ Uses existing database
- ✅ Data survives restarts

**Cons:**
- ❌ Slower than memcached/redis
- ❌ Database I/O overhead
- ❌ Can bloat database

---

## Option D: File-Based Cache

**Best for:** Local development only

### Configure Django
```python
# settings.py
import os
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': os.path.join('/tmp', 'django_cache'),
    }
}
```

**Pros:**
- ✅ Zero setup
- ✅ No external service

**Cons:**
- ❌ Slowest option
- ❌ File I/O on every operation
- ❌ Not recommended for production

---

## Testing Your Cache Setup

Run this in `python manage.py shell`:

```python
import multiprocessing
import time
from django.core.cache import cache

def child_process():
    """This runs in a separate process."""
    cache.set('test_key', 'from_child', timeout=60)

# Start child process
process = multiprocessing.Process(target=child_process)
process.start()
process.join()

# Check if parent can see child's cache write
time.sleep(0.5)
result = cache.get('test_key')

if result == 'from_child':
    print("✓ Cache backend works across processes!")
else:
    print("✗ Cache backend does NOT work across processes")
    print("  You're probably using locmem cache")
```

If you see "✗", your cache backend won't work with command-runner's multiprocessing.

---

## Performance Comparison

| Backend | Speed | Setup | Processes | Production |
|---------|-------|-------|-----------|------------|
| Memcached | ⚡⚡⚡ | Medium | ✅ | ✅ |
| Redis | ⚡⚡⚡ | Medium | ✅ | ✅ |
| Database | ⚡⚡ | Easy | ✅ | ⚠️ |
| File | ⚡ | Easy | ✅ | ❌ |
| Locmem | ⚡⚡⚡ | None | ❌ | ❌ |

---

## Troubleshooting

### "Command not finishing when I close the page"
- Your cache backend is probably `locmem`
- Check `settings.py` CACHES configuration
- Run the test script above

### "Connection refused to 127.0.0.1:11211"
- Memcached isn't running
- Check: `telnet localhost 11211`
- Start: `sudo systemctl start memcached`

### "Cache key errors"
- Check cache is configured correctly
- Try: `python manage.py shell` → `from django.core.cache import cache; cache.set('test', 'ok')`

### "Output not appearing"
- Check background process is running
- Look in Django logs for errors
- Verify cache backend works (use test script above)

---

## Migration from Locmem

If you're currently using the default Django cache (locmem):

1. Choose a cache backend from above
2. Install and configure it
3. Restart Django
4. Test with: `python test_background_execution.py`
5. Old cached data will be lost (expected)

---

## For Your Specific User

Based on the error logs showing `pylibmc.TooBig`, **you already have memcached running!**

You just need to:
1. `pip install pymemcache`
2. Add cache config to settings.py (Option A above)
3. Restart Django

That's it! No infrastructure changes needed.
