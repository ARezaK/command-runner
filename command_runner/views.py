import threading
import uuid
import json
import logging
import re
import sys
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
        try:
            current_output = self.getvalue()
            # Truncate if too large
            if len(current_output) > MAX_CACHE_SIZE:
                truncated_output = current_output[-MAX_CACHE_SIZE:] + "\n... (output truncated due to size limit)"
            else:
                truncated_output = current_output
                
            current = cache.get(self.cache_key) or {'output': '', 'error': '', 'finished': False}
            current['output'] = truncated_output
            cache.set(self.cache_key, current, timeout=3600)
        except Exception as e:
            # If cache fails, continue without caching to prevent command failure
            print(f"Cache update failed: {e}")
            pass


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

        # cache the help text for 24 hours
        cache.set(cache_key, help_text, 3600*24)
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
    command_list_cache_key = 'command_runner:command_list'
    cached_commands = cache.get(command_list_cache_key)
    
    if cached_commands:
        return render(request, 'command_runner/command_list.html', {
            'commands': cached_commands
        })
    
    # Get all available commands
    commands = get_commands()
    command_list = []

    for name, app in commands.items():
        # Don't include help text in initial load - it will be fetched via AJAX when needed
        command_list.append({
            'name': name,
            'app': app
        })
    
    # Sort the command list
    sorted_command_list = sorted(command_list, key=lambda x: x['name'])
    
    # Cache the sorted command list for 24 hour (or set a longer timeout if appropriate)
    cache.set(command_list_cache_key, sorted_command_list, 3600 * 24)

    return render(request, 'command_runner/command_list.html', {
        'commands': sorted_command_list
    })


# Store command outputs in cache
def get_command_key(command_id):
    return f'command_runner:{command_id}'


@staff_member_required
def start_command(request):
    data = json.loads(request.body)
    command_name = data.get('command')
    args = data.get('arguments', '').split()

    command_id = str(uuid.uuid4())
    cache_key = get_command_key(command_id)
    logging.getLogger('django.db.backends').setLevel(logging.WARNING)

    def run_command():
        stdout = FilteredStringIO(cache_key)
        stderr = FilteredStringIO(cache_key)
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
            except Exception as cache_error:
                # If cache still fails, store minimal info
                print(f"Final cache update failed: {cache_error}")
                cache.set(cache_key, {
                    'output': 'Command completed but output too large for cache',
                    'error': final_error[:1000] if final_error else '',
                    'finished': True
                }, timeout=3600)
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
            except Exception as cache_error:
                # If cache fails, store minimal error info
                print(f"Error cache update failed: {cache_error}")
                cache.set(cache_key, {
                    'output': 'Command failed and output too large for cache',
                    'error': error_message[:1000],
                    'finished': True
                }, timeout=3600)
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr

    # Initialize cache
    cache.set(cache_key, {
        'output': '',
        'error': '',
        'finished': False
    }, timeout=3600)

    # Run command in background
    thread = threading.Thread(target=run_command)
    thread.start()

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


@staff_member_required
def get_command_help_view(request):
    """API endpoint to fetch help text for a command."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            command_name = data.get('command')
            
            if not command_name:
                return JsonResponse({'error': 'Command name is required'}, status=400)
                
            help_text = get_command_help(command_name)
            return JsonResponse({'help': help_text})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Only POST requests are allowed'}, status=405)
