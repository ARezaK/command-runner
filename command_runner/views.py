import threading
import multiprocessing
import uuid
import json
import logging
import re
import sys
import os
import time
from io import StringIO
from django.shortcuts import render
from django.core.management import get_commands
from django.core.management import load_command_class
from django.core.management import call_command
from django.contrib.admin.views.decorators import staff_member_required
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie

# Maximum cache size to prevent TooBig errors (1MB)
MAX_CACHE_SIZE = 1024 * 1024

class FilteredStringIO(StringIO):
    def __init__(self, cache_key, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # We use a private buffer to accumulate text until we see a newline.
        self._buffer = ''
        # Flag to indicate we're in the middle of a multi-line SQL block.
        self.in_sql_block = False
        # Regular expression to match lines starting with SQL keywords.
        self.sql_pattern = re.compile(r'^(SELECT|INSERT|UPDATE|DELETE|FROM|WHERE|ORDER BY|LIMIT|Status for)\b', re.IGNORECASE)
        # Pattern to match progress indicators (more specific to avoid filtering legitimate output)
        self.progress_pattern = re.compile(r'(\r.*\|.*\|.*%|\r.*Downloading|\r.*Progress|.*\|\s*\d+%)', re.IGNORECASE)
        self.cache_key = cache_key

    def write(self, s):
        self._buffer += s
        # Split the buffer into lines; keep newline characters.
        lines = self._buffer.splitlines(keepends=True)
        # If the last line doesn't end with a newline, keep it in the buffer.
        if lines and not lines[-1].endswith('\n'):
            self._buffer = lines.pop()
        else:
            self._buffer = ''
        # Process each complete line.
        filtered_lines = []
        for line in lines:
            stripped = line.lstrip()
            
            # Skip progress indicators and download messages
            if self.progress_pattern.search(line):
                continue
                
            if not self.in_sql_block:
                # If the line starts with a SQL keyword, skip it and mark that we're in a SQL block.
                if self.sql_pattern.match(stripped):
                    self.in_sql_block = True
                    continue
                else:
                    filtered_lines.append(line)
            else:
                # We're in a SQL block; if the line is indented, assume it's a continuation and skip it.
                if line.startswith(' ') or line.startswith('\t'):
                    continue
                else:
                    # If the line is no longer indented, end the SQL block.
                    self.in_sql_block = False
                    # Re-check the new line – it might start a new SQL block.
                    if self.sql_pattern.match(line.lstrip()):
                        self.in_sql_block = True
                        continue
                    else:
                        filtered_lines.append(line)
        # Write the filtered lines to the underlying StringIO.
        super().write(''.join(filtered_lines))

        # Update the cache with the current output, but limit size
        # Only update cache periodically to reduce memcached load
        current_output = self.getvalue()

        # Initialize batching parameters on first write
        if not hasattr(self, '_last_cache_size'):
            self._last_cache_size = 0
            self._cache_update_interval = 1000  # Update every 1KB of new output
            self._last_cache_update_time = 0

        output_size = len(current_output)
        size_delta = output_size - self._last_cache_size

        # Update cache if:
        # 1. We have enough new data (size_delta >= interval), OR
        # 2. It's been a while since last update (time-based), OR
        # 3. This is the first write (last_cache_size == 0 and output_size > 0)
        current_time = time.time()
        time_since_update = current_time - self._last_cache_update_time

        should_update = (
            size_delta >= self._cache_update_interval or  # Size threshold
            (time_since_update >= 2.0 and size_delta > 0) or  # Time threshold (every 2 seconds)
            (self._last_cache_size == 0 and output_size > 0)  # First write
        )

        if should_update:
            try:
                # Truncate if too large (leave room for cache overhead)
                max_output = MAX_CACHE_SIZE - 10000  # Reserve 10KB for overhead
                if output_size > max_output:
                    truncated_output = current_output[-max_output:] + "\n... (output truncated due to size limit)"
                else:
                    truncated_output = current_output

                current = cache.get(self.cache_key)
                if current is None:
                    current = {'output': '', 'error': '', 'finished': False}
                current['output'] = truncated_output
                cache.set(self.cache_key, current, timeout=3600)
                self._last_cache_size = output_size
                self._last_cache_update_time = current_time
            except Exception:
                # If cache fails, continue without caching to prevent command failure
                # Don't retry on same error - just skip future updates
                # NOTE: Cannot use print() here as it would cause infinite recursion
                self._cache_update_interval = float('inf')  # Disable future cache updates


def get_command_help(command_name):
    """Get help text and arguments for a command."""
    # Check if help text is already in cache
    cache_key = f'command_help:{command_name}'
    cached_help = cache.get(cache_key)
    if cached_help:
        return cached_help
        
    try:
        # Create a string buffer to capture the output
        stdout = StringIO()
        stderr = StringIO()

        # Import the command class
        app_name = get_commands()[command_name]
        cmd = load_command_class(app_name, command_name)

        # Get the help text directly from the command class
        help_text = cmd.help

        # If the command has arguments, add them to the help text
        parser = cmd.create_parser('manage.py', command_name)
        help_text += '\n\nUsage: ' + parser.format_help()

        # cache the help text forever
        cache.set(cache_key, help_text, None)
        return help_text
    except Exception as e:
        return str(e)


@staff_member_required
@ensure_csrf_cookie
def command_list(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            command_name = data.get('command')
            args = data.get('arguments', '').split()

            # Capture the output
            stdout = StringIO()
            stderr = StringIO()

            print(f"Running command: {command_name} {args}")
            call_command(command_name, *args, stdout=stdout, stderr=stderr)
            output = stdout.getvalue()
            error = stderr.getvalue()
            print(f"Output: {output}")
            print(f"Error: {error}")
            return JsonResponse({'output': output, 'error': error})
        except Exception as e:
            return JsonResponse({'error': str(e)})

    # Check if command list is already in cache
    # Get all available commands
    commands = get_commands()
    command_list = []

    for name, app in commands.items():
        if 'django' in app:
            print(f"Skipped {name}:{app}")
            # ignore the default django management commands
            continue
        command_list.append({
            'name': name,
            'app': app,
            'help': get_command_help(name) if name != 'help' else None,
        })
    
    # Sort the command list
    sorted_command_list = sorted(command_list, key=lambda x: x['name'])

    return render(request, 'command_runner/command_list.html', {
        'commands': sorted_command_list
    })


# Store command outputs in cache
def get_command_key(command_id):
    return f'command_runner:{command_id}'


def run_command_in_process(command_name, args, cache_key):
    """
    Run a Django management command in a separate process.
    This function must be defined at module level for multiprocessing to work.
    """
    # In spawn mode, we need to set up Django fresh in the child process
    import os
    import django
    from django.conf import settings

    # Ensure DJANGO_SETTINGS_MODULE is set
    if not os.environ.get('DJANGO_SETTINGS_MODULE'):
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.settings')

    # Setup Django in child process
    if not settings.configured:
        django.setup()

    # Close inherited DB connections
    try:
        from django.db import connections
        connections.close_all()
    except Exception:
        pass

    # Import after Django is ready
    from django.core.management import call_command
    from django.core.cache import cache

    # Close any existing cache connections and recreate them in this process
    try:
        cache.close()
    except Exception:
        pass

    # Set logging level to reduce noise
    logging.getLogger('django.db.backends').setLevel(logging.WARNING)

    # Create filtered output streams
    stdout = FilteredStringIO(cache_key)
    stderr = FilteredStringIO(cache_key)

    # Replace sys.stdout and sys.stderr
    old_stdout, old_stderr = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = stdout, stderr

    try:
        call_command(command_name, *args)
        final_output = stdout.getvalue()
        final_error = stderr.getvalue()

        # Truncate output if too large for cache
        if len(final_output) > MAX_CACHE_SIZE:
            final_output = final_output[-MAX_CACHE_SIZE:] + "\n... (output truncated due to size limit)"
        if len(final_error) > MAX_CACHE_SIZE:
            final_error = final_error[-MAX_CACHE_SIZE:] + "\n... (error output truncated due to size limit)"

        try:
            cache.set(cache_key, {
                'output': final_output,
                'error': final_error,
                'finished': True
            }, timeout=3600)
        except Exception:
            # If cache still fails, store minimal info
            # NOTE: Cannot use print() as stdout is redirected to FilteredStringIO
            try:
                cache.set(cache_key, {
                    'output': 'Command completed but output too large for cache',
                    'error': final_error[:1000] if final_error else '',
                    'finished': True
                }, timeout=3600)
            except Exception:
                # Last resort: mark as finished with error message
                pass
    except Exception as e:
        error_output = stdout.getvalue()
        error_message = str(e)

        # Truncate if too large
        if len(error_output) > MAX_CACHE_SIZE:
            error_output = error_output[-MAX_CACHE_SIZE:] + "\n... (output truncated due to size limit)"

        try:
            cache.set(cache_key, {
                'output': error_output,
                'error': error_message,
                'finished': True
            }, timeout=3600)
        except Exception:
            # If cache fails, store minimal error info
            # NOTE: Cannot use print() as stdout is redirected to FilteredStringIO
            try:
                cache.set(cache_key, {
                    'output': 'Command failed and output too large for cache',
                    'error': error_message[:1000],
                    'finished': True
                }, timeout=3600)
            except Exception:
                # Last resort: just fail silently
                pass
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr


@staff_member_required
def start_command(request):
    data = json.loads(request.body)
    command_name = data.get('command')
    args = data.get('arguments', '').split()

    command_id = str(uuid.uuid4())
    cache_key = get_command_key(command_id)

    # Initialize cache
    cache.set(cache_key, {
        'output': '',
        'error': '',
        'finished': False
    }, timeout=3600)

    # Run command in a separate process (daemon=True means it won't block parent process shutdown)
    # Using 'spawn' method for better cross-platform compatibility and isolation
    ctx = multiprocessing.get_context('spawn')
    process = ctx.Process(
        target=run_command_in_process,
        args=(command_name, args, cache_key),
        daemon=False  # Don't use daemon so command can complete even if Django restarts
    )
    process.start()

    return JsonResponse({'command_id': command_id})


@staff_member_required
def command_status(request, command_id):
    cache_key = get_command_key(command_id)
    status = cache.get(cache_key)

    if status is None:
        return JsonResponse({
            'error': 'Command not found or expired',
            'finished': True
        })

    # Add print statements for debugging
    print(f"Status for {command_id}: {status}")
    return JsonResponse(status)
