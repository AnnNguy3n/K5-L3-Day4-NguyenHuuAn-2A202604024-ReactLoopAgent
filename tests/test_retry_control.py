"""Kiểm tra giới hạn gọi API và cooldown, không gọi mạng hay chờ thật."""
import unittest
from unittest.mock import Mock, patch

from agent import run_agent, retry_delay
from test_lab import FakeProvider, tool_call, final


class RetryControlTests(unittest.TestCase):
    def run_script(self, retry_after, attempts):
        tools = Mock(spec=['execute'])
        tools.execute.return_value = {'ok': False, 'error': 'RATE_LIMITED',
                                     'retry_after': retry_after}
        provider = FakeProvider([
            tool_call(str(i), 'get_status', '{"provider":"github"}')
            for i in range(attempts)
        ] + [final('Không xác minh được status')])
        with patch('agent.time.monotonic', return_value=0), patch('agent.time.sleep') as sleep:
            result = run_agent('Kiểm tra', provider, tools, max_steps=attempts + 1)
        return tools, result, sleep

    def test_persistent_429_never_exceeds_three_requests(self):
        tools, result, _ = self.run_script('0', 4)
        self.assertEqual(tools.execute.call_count, 3)
        events = [t for t in result['trace'] if t['event'] == 'tool']
        self.assertEqual(events[2]['result']['retries_remaining'], 0)
        self.assertFalse(events[2]['result']['retriable'])
        self.assertEqual(events[-1]['result']['error'], 'RETRY_LIMIT')

    def test_retry_after_is_honored(self):
        tools, result, sleep = self.run_script('2', 2)
        self.assertEqual(tools.execute.call_count, 2)
        sleep.assert_called_once_with(2)
        self.assertTrue(any(t['event'] == 'retry_wait' for t in result['trace']))

    def test_long_or_invalid_retry_after_stops_without_sleep(self):
        for header in ('3600', 'invalid', 'NaN', 'Infinity'):
            with self.subTest(header=header):
                tools, result, sleep = self.run_script(header, 2)
                self.assertEqual(tools.execute.call_count, 1)
                sleep.assert_not_called()
                events = [t for t in result['trace'] if t['event'] == 'tool']
                self.assertEqual(events[-1]['result']['error'], 'RETRY_BUDGET_EXCEEDED')

    def test_http_date_retry_after(self):
        from datetime import datetime, timedelta, timezone
        from email.utils import format_datetime
        header = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=60))
        self.assertTrue(58 <= retry_delay({'retry_after': header}) <= 60)
