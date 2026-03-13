"""Tests for the CLI interface."""

from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner

from agent_verify.cli import main
from agent_verify.models.report import Verdict, VerifyReport


class TestCLI:
    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_info_command(self):
        runner = CliRunner()
        result = runner.invoke(main, ["info"])
        assert result.exit_code == 0
        assert "agent-verify" in result.output
        assert "python" in result.output.lower()

    @patch("agent_verify.cli.run_pipeline")
    def test_check_pass(self, mock_pipeline):
        mock_pipeline.return_value = VerifyReport(
            verdict=Verdict.PASS,
            confidence_score=0.95,
            claims_verified=3,
            claims_total=3,
        )
        runner = CliRunner()
        result = runner.invoke(main, ["check", "--repo", "."])
        assert result.exit_code == 0

    @patch("agent_verify.cli.run_pipeline")
    def test_check_fail_exits_1(self, mock_pipeline):
        mock_pipeline.return_value = VerifyReport(
            verdict=Verdict.FAIL,
            confidence_score=0.2,
        )
        runner = CliRunner()
        result = runner.invoke(main, ["check", "--repo", "."])
        assert result.exit_code == 1

    @patch("agent_verify.cli.run_pipeline")
    def test_check_warn_exits_0_by_default(self, mock_pipeline):
        mock_pipeline.return_value = VerifyReport(
            verdict=Verdict.WARN,
            confidence_score=0.5,
        )
        runner = CliRunner()
        result = runner.invoke(main, ["check", "--repo", "."])
        assert result.exit_code == 0

    @patch("agent_verify.cli.run_pipeline")
    def test_check_warn_exits_1_with_flag(self, mock_pipeline):
        mock_pipeline.return_value = VerifyReport(
            verdict=Verdict.WARN,
            confidence_score=0.5,
        )
        runner = CliRunner()
        result = runner.invoke(main, ["check", "--repo", ".", "--fail-on-warn"])
        assert result.exit_code == 1

    @patch("agent_verify.cli.run_pipeline")
    def test_check_json_output(self, mock_pipeline):
        mock_pipeline.return_value = VerifyReport(
            verdict=Verdict.PASS,
            confidence_score=0.9,
        )
        runner = CliRunner()
        result = runner.invoke(main, ["check", "--repo", ".", "--json-output"])
        assert result.exit_code == 0
        assert '"verdict"' in result.output
        assert '"pass"' in result.output

    def test_check_pr_body_file_not_found(self):
        runner = CliRunner()
        result = runner.invoke(main, ["check", "--pr-body-file", "/nonexistent/file.md"])
        assert result.exit_code == 2

    def test_add_claim(self):
        runner = CliRunner()
        result = runner.invoke(main, ["add-claim", "Users can log in via OAuth2"])
        assert result.exit_code == 0
        assert "Added claim" in result.output
