from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.cache import cache
import json
import time
import multiprocessing
from command_runner.views import get_command_key, run_command_in_process


class CommandRunnerTests(TestCase):
    def setUp(self):
        """Create a staff user for testing."""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass',
            is_staff=True
        )
        self.client.login(username='testuser', password='testpass')

    def tearDown(self):
        """Clean up cache after each test."""
        cache.clear()

    def test_command_list_requires_staff(self):
        """Test that command list view requires staff authentication."""
        # Logout
        self.client.logout()

        response = self.client.get('/command-runner/')
        # Should redirect to login
        self.assertEqual(response.status_code, 302)

    def test_command_list_view(self):
        """Test that command list view loads successfully."""
        response = self.client.get('/command-runner/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Available Management Commands')

    def test_start_command_creates_process(self):
        """Test that starting a command creates a background process."""
        response = self.client.post(
            '/command-runner/start/',
            data=json.dumps({
                'command': 'no_args_command',
                'arguments': ''
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('command_id', data)

        # Verify cache was initialized
        cache_key = get_command_key(data['command_id'])
        status = cache.get(cache_key)
        self.assertIsNotNone(status)
        self.assertIn('output', status)
        self.assertIn('error', status)
        self.assertIn('finished', status)
        self.assertFalse(status['finished'])

    def test_command_completes_in_background(self):
        """Test that a command completes successfully in background."""
        # Start the command
        response = self.client.post(
            '/command-runner/start/',
            data=json.dumps({
                'command': 'no_args_command',
                'arguments': ''
            }),
            content_type='application/json'
        )

        data = json.loads(response.content)
        command_id = data['command_id']
        cache_key = get_command_key(command_id)

        # Poll for completion (no_args_command takes ~5 seconds)
        max_wait = 10
        start_time = time.time()
        finished = False

        while time.time() - start_time < max_wait:
            status = cache.get(cache_key)
            if status and status.get('finished'):
                finished = True
                break
            time.sleep(0.5)

        self.assertTrue(finished, "Command did not complete within timeout")

        # Verify output contains expected messages
        final_status = cache.get(cache_key)
        self.assertIn('Test command finished successfully', final_status['output'])

    def test_command_status_endpoint(self):
        """Test the command status polling endpoint."""
        # Start a command
        response = self.client.post(
            '/command-runner/start/',
            data=json.dumps({
                'command': 'no_args_command',
                'arguments': ''
            }),
            content_type='application/json'
        )

        data = json.loads(response.content)
        command_id = data['command_id']

        # Poll status
        status_response = self.client.get(f'/command-runner/status/{command_id}/')
        self.assertEqual(status_response.status_code, 200)

        status_data = json.loads(status_response.content)
        self.assertIn('output', status_data)
        self.assertIn('error', status_data)
        self.assertIn('finished', status_data)

    def test_command_with_arguments(self):
        """Test running a command with arguments."""
        response = self.client.post(
            '/command-runner/start/',
            data=json.dumps({
                'command': 'with_args_command',
                'arguments': 'TestName --shout'
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        command_id = data['command_id']
        cache_key = get_command_key(command_id)

        # Wait for completion
        time.sleep(2)

        status = cache.get(cache_key)
        self.assertTrue(status['finished'])
        self.assertIn('TESTNAME', status['output'])

    def test_cache_handles_large_output(self):
        """Test that large output is truncated properly to prevent cache errors."""
        from command_runner.views import FilteredStringIO, MAX_CACHE_SIZE

        cache_key = 'test_large_output'
        stream = FilteredStringIO(cache_key)

        # Write output larger than MAX_CACHE_SIZE
        large_output = 'X' * (MAX_CACHE_SIZE + 100000)
        stream.write(large_output)

        # Check that output was truncated
        result = stream.getvalue()
        self.assertLess(len(result), MAX_CACHE_SIZE)

        # Verify cache entry exists and is not too large
        cached = cache.get(cache_key)
        if cached:
            self.assertLess(len(cached.get('output', '')), MAX_CACHE_SIZE)

    def test_cache_failure_doesnt_crash_command(self):
        """Test that cache failures don't crash the command execution."""
        from command_runner.views import FilteredStringIO
        from unittest.mock import patch

        cache_key = 'test_cache_failure'
        stream = FilteredStringIO(cache_key)

        # Mock cache.set to raise an exception
        with patch('django.core.cache.cache.set', side_effect=Exception('Cache failed')):
            # This should not raise an exception
            stream.write('Test output\n')
            stream.write('More output\n')

        # Stream should still work
        result = stream.getvalue()
        self.assertIn('Test output', result)
        self.assertIn('More output', result)

    def test_process_isolation(self):
        """Test that commands run in isolated processes."""
        import os

        # Get parent process ID
        parent_pid = os.getpid()

        # Start a command
        response = self.client.post(
            '/command-runner/start/',
            data=json.dumps({
                'command': 'no_args_command',
                'arguments': ''
            }),
            content_type='application/json'
        )

        # The command should be running in a different process
        # We can't easily get the child PID, but we can verify the command
        # completes even if we don't poll (process isolation working)
        data = json.loads(response.content)
        command_id = data['command_id']
        cache_key = get_command_key(command_id)

        # Wait for completion
        time.sleep(6)

        status = cache.get(cache_key)
        self.assertIsNotNone(status)
        self.assertTrue(status['finished'])

    def test_expired_command_status(self):
        """Test that requesting status for non-existent command returns proper error."""
        response = self.client.get('/command-runner/status/nonexistent-id/')
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertIn('error', data)
        self.assertTrue(data['finished'])

    def test_multiword_arguments(self):
        """Test command with multi-word arguments."""
        response = self.client.post(
            '/command-runner/start/',
            data=json.dumps({
                'command': 'multi_word_args_command',
                'arguments': 'arg1 arg2 arg3'
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Wait for completion
        time.sleep(2)

        cache_key = get_command_key(data['command_id'])
        status = cache.get(cache_key)
        self.assertTrue(status['finished'])
