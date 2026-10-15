"""Every frontend receives the same shell implementation and explicit gate."""

import unittest

from local_cli.tools import create_tools
from local_cli.tools.bash_tool import BashTool
from local_cli.shell_executor import ShellDescriptor
from local_cli.prompts import build_system_prompt


def command_tool(tools):
    return next(tool for tool in tools if tool.name == "bash")


class TestFrontendFactories(unittest.TestCase):
    def test_public_name_is_compatible_everywhere(self):
        for frontend in ("cli", "server", "sub_agent"):
            with self.subTest(frontend=frontend):
                kwargs = {"confirm": lambda _command: False} if frontend in ("cli", "server") else {}
                tool = command_tool(create_tools(frontend, **kwargs))
                self.assertIsInstance(tool, BashTool)
                self.assertEqual(tool.name, "bash")

    def test_cli_and_server_require_approval_callback(self):
        for frontend in ("cli", "server"):
            with self.subTest(frontend=frontend):
                with self.assertRaises(ValueError):
                    create_tools(frontend)

    def test_unattended_frontends_deny_risky_commands(self):
        for frontend in ("sub_agent",):
            with self.subTest(frontend=frontend):
                tool = command_tool(create_tools(frontend))
                self.assertIn("declined", tool.execute(command="sudo echo no").lower())

    def test_explicit_auto_approve_preserves_existing_behavior(self):
        for frontend in ("cli", "server"):
            with self.subTest(frontend=frontend):
                tool = command_tool(create_tools(frontend, auto_approve=True))
                self.assertIsNone(tool._confirm)

    def test_sub_agents_never_auto_approve(self):
        tool = command_tool(create_tools("sub_agent", auto_approve=True))
        self.assertIsNotNone(tool._confirm)
        self.assertIn("declined", tool.execute(command="sudo echo no").lower())

    def test_model_gets_trusted_host_shell_context_without_shell_argument(self):
        descriptor = ShellDescriptor("Windows", "powershell", "pwsh.exe", "7.6")
        tool = BashTool(descriptor=descriptor)
        prompt = build_system_prompt([tool])
        self.assertIn("HOST OS: Windows", prompt)
        self.assertIn("SELECTED SHELL: powershell 7.6", prompt)
        self.assertIn("SHELL CAPABILITIES:", prompt)
        self.assertNotIn("shell", tool.parameters["properties"])
        self.assertEqual(tool.name, "bash")


if __name__ == "__main__":
    unittest.main()
