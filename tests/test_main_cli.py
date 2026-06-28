"""
Tests for main.py CLI entry point.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture()
def cli_runner(monkeypatch, tmp_path):
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.is_production = False
    settings.sentry_dsn = ""
    settings.sentry_environment = "development"
    settings.sentry_sample_rate = 1.0
    settings.validate_config.return_value = True
    monkeypatch.setattr("main.settings", settings)

    csv = MagicMock()
    csv.return_value = MagicMock()
    monkeypatch.setattr("main.setup_signal_handlers", MagicMock())
    monkeypatch.setattr("main.validate_environment", lambda: {"issues": [], "warnings": []})
    monkeypatch.setattr("main.get_health_check_summary", lambda: {"overall_status": "healthy"})
    monkeypatch.setattr("main.init_db", MagicMock())
    monkeypatch.setattr("main.setup_logging", MagicMock())

    with patch.object(Path, "cwd", return_value=tmp_path):
        yield {"settings": settings, "tmp_path": tmp_path}


class TestHealthCheck:
    def test_health_check_returns_healthy_exit_code(self, cli_runner, monkeypatch, capsys):
        import main

        with pytest.raises(SystemExit) as exc_info:
            with patch.object(sys, "argv", ["main.py", "health-check"]):
                main.main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "healthy" in captured.out


class TestInitCommand:
    def test_init_creates_database_tables(self, cli_runner, monkeypatch):
        import main

        mock_init_db = MagicMock()
        monkeypatch.setattr("main.init_db", mock_init_db)

        with patch.object(sys, "argv", ["main.py", "init"]):
            main.main()

        mock_init_db.assert_called_once()


class TestScrapeCommand:
    def test_scrape_olx_runs_without_crashing(
        self, cli_runner, monkeypatch, capsys, tmp_path
    ):
        import main

        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/autodeal.db")
        monkeypatch.setattr("main.validate_environment", lambda: {"issues": [], "warnings": []})

        mock_scraper = MagicMock()
        mock_scraper.scrape_listings = MagicMock(return_value=asyncio_coroutine([]))
        mock_browser_pool = MagicMock()
        mock_browser_pool.get_stats.return_value = {"active": 0}

        with patch.object(sys, "argv", ["main.py", "scrape", "--source", "olx", "--max-listings", "1"]), \
             patch("scrapers.OLXScraper", return_value=mock_scraper), \
             patch("scrapers.browser_pool.get_browser_pool", return_value=mock_browser_pool), \
             patch("processing.pipeline.production_pipeline.process_batch", return_value={"total": 0, "success": 0, "error": 0, "avg_score": 0.0, "processing_time": 0.0}), \
             patch("main.asyncio.run"):
            main.main()


class TestInvalidArgs:
    def test_invalid_args_are_rejected(self, cli_runner, capsys):
        import main

        invalid_args = [
            ["main.py", "scrape", "--source", "invalid_source"],
            ["main.py", "scrape", "--max-listings", "-5"],
            ["main.py", "unknown_command"],
        ]

        for argv in invalid_args:
            with pytest.raises(SystemExit) as exc_info:
                with patch.object(sys, "argv", argv):
                    main.main()
            assert exc_info.value.code != 0


def asyncio_coroutine(return_value):
    async def _coro(*args, **kwargs):
        return return_value

    return _coro
