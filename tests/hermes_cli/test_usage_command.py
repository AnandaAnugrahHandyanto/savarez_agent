import json
import unittest
from unittest.mock import MagicMock, patch
from hermes_cli.usage_command import cmd_usage

class TestUsageCommand(unittest.TestCase):
    @patch("hermes_cli.usage_command.SessionDB")
    @patch("hermes_cli.usage_command.fetch_account_usage")
    def test_cmd_usage_text(self, mock_fetch, mock_db):
        # Mock DB
        mock_conn = MagicMock()
        mock_db.return_value._conn = mock_conn
        mock_db.return_value._lock = MagicMock().__enter__.return_value
        
        mock_cursor = mock_conn.execute.return_value
        mock_cursor.fetchone.return_value = (
            "session-123", "gpt-4", "openai", "http://api.com",
            100, 50, 10, 5, 2
        )

        # Mock fetch_account_usage
        mock_fetch.return_value = None

        args = MagicMock()
        args.json = False
        
        with patch("sys.stdout") as mock_stdout:
            cmd_usage(args)
            
        output = "".join(call.args[0] for call in mock_stdout.write.call_args_list)
        self.assertIn("gpt-4", output)
        self.assertIn("Total:", output)
        self.assertIn("165", output)

    @patch("hermes_cli.usage_command.SessionDB")
    @patch("hermes_cli.usage_command.fetch_account_usage")
    def test_cmd_usage_json(self, mock_fetch, mock_db):
        # Mock DB
        mock_conn = MagicMock()
        mock_db.return_value._conn = mock_conn
        mock_db.return_value._lock = MagicMock().__enter__.return_value
        
        mock_cursor = mock_conn.execute.return_value
        mock_cursor.fetchone.return_value = (
            "session-123", "gpt-4", "openai", "http://api.com",
            100, 50, 10, 5, 2
        )

        # Mock fetch_account_usage
        mock_fetch.return_value = None

        args = MagicMock()
        args.json = True
        
        with patch("sys.stdout") as mock_stdout:
            cmd_usage(args)
            
        output = "".join(call.args[0] for call in mock_stdout.write.call_args_list)
        data = json.loads(output)
        self.assertEqual(data["session_id"], "session-123")
        self.assertEqual(data["tokens"]["total"], 165)

if __name__ == "__main__":
    unittest.main()
