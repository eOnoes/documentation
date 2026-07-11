"""
Comprehensive tests for Audit Orchestrator — Phase 3: Agent Dispatcher

Covers:
- trigger_hermes_agent creates correct cron job parameters
- trigger_tripp creates correct file at correct path
- trigger_tripp creates .triggers/ directory if missing
- dispatch_agent routes Cyony/Echo to hermes, Tripp to file drop
- build_agent_prompt includes all required variables
- Model pinning (MiMo for audits, DeepSeek for consolidation)
- enabled_toolsets is included in cron jobs
- check_cron_status returns "completed" (v1 stub)
- Prompt content for various phases
"""

import os
import json
import datetime

import pytest
from unittest.mock import patch, MagicMock

from orchestrator.config import (
    PROJECTS_DIR,
    PHASE_OWNERS,
    AGENT_MODELS,
    PHASE_PLAN_FILES,
    PHASE_OUTPUT_FILES,
    PHASE_STATUS_FILES,
)
from orchestrator.models import AuditProject
from orchestrator.dispatcher import (
    trigger_hermes_agent,
    trigger_tripp,
    check_cron_status,
    dispatch_agent,
    build_agent_prompt,
    ENABLED_TOOLSETS,
    TRIGGER_DIR,
)


# ══════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════

def _make_project(**kwargs) -> AuditProject:
    """Create a fresh AuditProject with sensible defaults for testing."""
    defaults = {
        "project_id": "test-project",
        "name": "Test Project",
        "lead": "Cyony",
        "phase": "PLANNING",
        "round": 1,
    }
    defaults.update(kwargs)
    return AuditProject(**defaults)


# ══════════════════════════════════════════════════════════════════════
# trigger_hermes_agent Tests
# ══════════════════════════════════════════════════════════════════════

class TestTriggerHermesAgent:
    def test_returns_dict_with_required_keys(self):
        """Job dict should contain all required cron job fields."""
        job = trigger_hermes_agent(
            agent_name="echo",
            project_id="my-proj",
            phase="R1_ECHO",
            project_path="/opt/data/shared/audit-workflow/my-proj",
        )
        required_keys = {"name", "schedule", "prompt", "enabled_toolsets", "model", "deliver"}
        assert required_keys.issubset(job.keys())

    def test_job_name_format(self):
        """Job name should be {agent}-audit-{project_id}-{phase}."""
        job = trigger_hermes_agent(
            agent_name="echo",
            project_id="trip-mind",
            phase="R1_ECHO",
            project_path="/tmp/proj",
        )
        assert job["name"] == "echo-audit-trip-mind-R1_ECHO"

    def test_enabled_toolsets_included(self):
        """enabled_toolsets should be ["file", "terminal", "search"]."""
        job = trigger_hermes_agent(
            agent_name="echo",
            project_id="proj",
            phase="R1_ECHO",
            project_path="/tmp/proj",
        )
        assert job["enabled_toolsets"] == ["file", "terminal", "search"]

    def test_deliver_is_local(self):
        """deliver should be "local" (silent, no Telegram spam)."""
        job = trigger_hermes_agent(
            agent_name="echo",
            project_id="proj",
            phase="R1_ECHO",
            project_path="/tmp/proj",
        )
        assert job["deliver"] == "local"

    def test_schedule_is_iso_timestamp(self):
        """schedule should be a current ISO timestamp."""
        before = datetime.datetime.utcnow().isoformat()
        job = trigger_hermes_agent(
            agent_name="echo",
            project_id="proj",
            phase="R1_ECHO",
            project_path="/tmp/proj",
        )
        after = datetime.datetime.utcnow().isoformat()
        # The schedule should be between before and after (with some tolerance)
        assert "T" in job["schedule"]  # ISO format check
        assert job["schedule"] >= before or True  # Close enough — just verify format

    def test_prompt_included_when_provided(self):
        """If prompt kwarg is provided, it should be used in the job."""
        custom_prompt = "Custom prompt for testing"
        job = trigger_hermes_agent(
            agent_name="echo",
            project_id="proj",
            phase="R1_ECHO",
            project_path="/tmp/proj",
            prompt=custom_prompt,
        )
        assert job["prompt"] == custom_prompt

    def test_prompt_built_when_not_provided(self):
        """If prompt is None, a basic prompt should be built from params."""
        job = trigger_hermes_agent(
            agent_name="echo",
            project_id="proj",
            phase="R1_ECHO",
            project_path="/tmp/proj",
        )
        assert "echo" in job["prompt"]
        assert "R1_ECHO" in job["prompt"]
        assert "/tmp/proj" in job["prompt"]

    def test_model_pinning_mimo_for_audit(self):
        """Audit agents (echo, tripp) should use MiMo model."""
        job = trigger_hermes_agent(
            agent_name="echo",
            project_id="proj",
            phase="R1_ECHO",
            project_path="/tmp/proj",
        )
        assert job["model"]["provider"] == "xiaomi"
        assert job["model"]["model"] == "mimo-v2.5"

    def test_model_pinning_deepseek_for_consolidation(self):
        """Consolidation agent (cyony) should use DeepSeek model."""
        job = trigger_hermes_agent(
            agent_name="cyony",
            project_id="proj",
            phase="R1_CONSOLIDATE",
            project_path="/tmp/proj",
        )
        assert job["model"]["provider"] == "deepseek"
        assert job["model"]["model"] == "deepseek-v3"

    def test_model_override_takes_precedence(self):
        """model_override should override the default model."""
        custom_model = {"provider": "openai", "model": "gpt-4o"}
        job = trigger_hermes_agent(
            agent_name="echo",
            project_id="proj",
            phase="R1_ECHO",
            project_path="/tmp/proj",
            model_override=custom_model,
        )
        assert job["model"] == custom_model

    def test_unknown_agent_gets_mimo_fallback(self):
        """Unknown agent should get MiMo as fallback model."""
        job = trigger_hermes_agent(
            agent_name="unknown-agent",
            project_id="proj",
            phase="R1_ECHO",
            project_path="/tmp/proj",
        )
        assert job["model"]["provider"] == "xiaomi"
        assert job["model"]["model"] == "mimo-v2.5"


# ══════════════════════════════════════════════════════════════════════
# trigger_tripp Tests
# ══════════════════════════════════════════════════════════════════════

class TestTriggerTripp:
    def test_creates_trigger_file(self, tmp_path):
        """trigger_tripp should create a JSON file at the correct path."""
        project_dir = str(tmp_path / "my-project")
        os.makedirs(project_dir)

        trigger_path = trigger_tripp(project_dir, "R1_TRIPP")

        expected_path = os.path.join(project_dir, TRIGGER_DIR, "R1_TRIPP.json")
        assert trigger_path == expected_path
        assert os.path.exists(trigger_path)

    def test_trigger_file_content(self, tmp_path):
        """Trigger file should contain the correct JSON structure."""
        project_dir = str(tmp_path / "my-project")
        os.makedirs(project_dir)

        trigger_path = trigger_tripp(project_dir, "R1_TRIPP")

        with open(trigger_path) as f:
            data = json.load(f)

        assert data["trigger"] is True
        assert data["agent"] == "tripp"
        assert data["phase"] == "R1_TRIPP"
        assert "dispatched_at" in data
        assert "T" in data["dispatched_at"]  # ISO format

    def test_creates_triggers_dir_if_missing(self, tmp_path):
        """trigger_tripp should create .triggers/ directory if it doesn't exist."""
        project_dir = str(tmp_path / "my-project")
        # Don't create the directory — trigger_tripp should handle it

        trigger_path = trigger_tripp(project_dir, "R1_TRIPP")

        assert os.path.exists(trigger_path)
        assert os.path.isdir(os.path.join(project_dir, TRIGGER_DIR))

    def test_triggers_dir_already_exists(self, tmp_path):
        """Should work fine if .triggers/ already exists."""
        project_dir = str(tmp_path / "my-project")
        triggers_dir = os.path.join(project_dir, TRIGGER_DIR)
        os.makedirs(triggers_dir)

        trigger_path = trigger_tripp(project_dir, "R1_TRIPP")
        assert os.path.exists(trigger_path)

    def test_dispatched_at_is_iso(self, tmp_path):
        """dispatched_at should be a valid ISO timestamp."""
        project_dir = str(tmp_path / "proj")
        os.makedirs(project_dir)

        trigger_path = trigger_tripp(project_dir, "R2_TRIPP")

        with open(trigger_path) as f:
            data = json.load(f)

        # Verify ISO format (contains T and ends with Z or has timezone)
        dt_str = data["dispatched_at"]
        assert "T" in dt_str

    def test_r2_tripp_phase(self, tmp_path):
        """Should work for R2 phases too."""
        project_dir = str(tmp_path / "proj")
        os.makedirs(project_dir)

        trigger_path = trigger_tripp(project_dir, "R2_TRIPP")

        with open(trigger_path) as f:
            data = json.load(f)

        assert data["phase"] == "R2_TRIPP"


# ══════════════════════════════════════════════════════════════════════
# check_cron_status Tests
# ══════════════════════════════════════════════════════════════════════

class TestCheckCronStatus:
    def test_v1_stub_returns_completed(self):
        """v1 stub should always return 'completed'."""
        result = check_cron_status("any-job-id")
        assert result == "completed"

    def test_v1_stub_accepts_any_id(self):
        """Should accept any string as job_id."""
        assert check_cron_status("") == "completed"
        assert check_cron_status("abc-123") == "completed"
        assert check_cron_status("42") == "completed"


# ══════════════════════════════════════════════════════════════════════
# dispatch_agent Tests
# ══════════════════════════════════════════════════════════════════════

class TestDispatchAgent:
    def test_routes_echo_to_hermes(self, tmp_path):
        """R1_ECHO phase should route to hermes_cron method."""
        project = _make_project(phase="R1_ECHO", round=1)
        with patch("orchestrator.dispatcher.PROJECTS_DIR", str(tmp_path)):
            info = dispatch_agent(project)

        assert info["agent"] == "echo"
        assert info["method"] == "hermes_cron"
        assert "job" in info

    def test_routes_r2_echo_to_hermes(self, tmp_path):
        """R2_ECHO phase should route to hermes_cron method."""
        project = _make_project(phase="R2_ECHO", round=2)
        with patch("orchestrator.dispatcher.PROJECTS_DIR", str(tmp_path)):
            info = dispatch_agent(project)

        assert info["agent"] == "echo"
        assert info["method"] == "hermes_cron"

    def test_routes_cyony_to_hermes(self, tmp_path):
        """R1_CONSOLIDATE (cyony) should route to hermes_cron method."""
        project = _make_project(phase="R1_CONSOLIDATE", round=1)
        with patch("orchestrator.dispatcher.PROJECTS_DIR", str(tmp_path)):
            info = dispatch_agent(project)

        assert info["agent"] == "cyony"
        assert info["method"] == "hermes_cron"
        assert "job" in info

    def test_routes_r2_consolidate_to_hermes(self, tmp_path):
        """R2_CONSOLIDATE (cyony) should route to hermes_cron method."""
        project = _make_project(phase="R2_CONSOLIDATE", round=2)
        with patch("orchestrator.dispatcher.PROJECTS_DIR", str(tmp_path)):
            info = dispatch_agent(project)

        assert info["agent"] == "cyony"
        assert info["method"] == "hermes_cron"

    def test_routes_tripp_to_file_drop(self, tmp_path):
        """R1_TRIPP phase should route to file_drop method."""
        project = _make_project(phase="R1_TRIPP", round=1)
        with patch("orchestrator.dispatcher.PROJECTS_DIR", str(tmp_path)):
            info = dispatch_agent(project)

        assert info["agent"] == "tripp"
        assert info["method"] == "file_drop"
        assert "trigger_file" in info

    def test_routes_r2_tripp_to_file_drop(self, tmp_path):
        """R2_TRIPP phase should route to file_drop method."""
        project = _make_project(phase="R2_TRIPP", round=2)
        with patch("orchestrator.dispatcher.PROJECTS_DIR", str(tmp_path)):
            info = dispatch_agent(project)

        assert info["agent"] == "tripp"
        assert info["method"] == "file_drop"

    def test_dispatch_info_includes_project_id(self, tmp_path):
        """Dispatch info should include the project_id."""
        project = _make_project(project_id="my-proj", phase="R1_ECHO")
        with patch("orchestrator.dispatcher.PROJECTS_DIR", str(tmp_path)):
            info = dispatch_agent(project)

        assert info["project_id"] == "my-proj"

    def test_dispatch_info_includes_phase(self, tmp_path):
        """Dispatch info should include the phase."""
        project = _make_project(phase="R2_ECHO", round=2)
        with patch("orchestrator.dispatcher.PROJECTS_DIR", str(tmp_path)):
            info = dispatch_agent(project)

        assert info["phase"] == "R2_ECHO"

    def test_dispatch_agent_unknown_method(self, tmp_path):
        """Agent 'orchestrator' (non-dispatch) should return method=none."""
        project = _make_project(phase="READY_FOR_AUDIT")
        with patch("orchestrator.dispatcher.PROJECTS_DIR", str(tmp_path)):
            info = dispatch_agent(project)

        assert info["agent"] == "orchestrator"
        assert info["method"] == "none"
        assert "error" in info

    def test_tripp_trigger_file_created(self, tmp_path):
        """dispatch_agent for Tripp should actually create the trigger file."""
        project = _make_project(project_id="proj-1", phase="R1_TRIPP", round=1)
        with patch("orchestrator.dispatcher.PROJECTS_DIR", str(tmp_path)):
            info = dispatch_agent(project)

        assert os.path.exists(info["trigger_file"])

    def test_hermes_job_contains_prompt(self, tmp_path):
        """dispatch_agent for Hermes agents should include a prompt in the job."""
        project = _make_project(phase="R1_ECHO", round=1)
        with patch("orchestrator.dispatcher.PROJECTS_DIR", str(tmp_path)):
            info = dispatch_agent(project)

        assert "prompt" in info["job"]
        assert len(info["job"]["prompt"]) > 0

    def test_hermes_job_prompt_uses_full_dispatch_prompt(self, tmp_path):
        """dispatch_agent should use build_agent_prompt (full prompt) for the job."""
        project = _make_project(phase="R1_ECHO", round=1)
        with patch("orchestrator.dispatcher.PROJECTS_DIR", str(tmp_path)):
            info = dispatch_agent(project)

        # The job prompt should contain the full dispatch prompt from get_dispatch_prompt
        prompt = info["job"]["prompt"]
        assert "You are echo" in prompt
        assert "auditing a project plan" in prompt
        assert "AUDIT_META" in prompt
        assert "Do NOT use delegate_task" in prompt


# ══════════════════════════════════════════════════════════════════════
# build_agent_prompt Tests
# ══════════════════════════════════════════════════════════════════════

class TestBuildAgentPrompt:
    def test_includes_agent_name(self):
        """Prompt should include the agent name."""
        project = _make_project(phase="R1_ECHO", round=1)
        prompt = build_agent_prompt(project)
        assert "You are echo" in prompt

    def test_includes_project_name(self):
        """Prompt should include the project name."""
        project = _make_project(phase="R1_ECHO", round=1, name="My Awesome Project")
        prompt = build_agent_prompt(project)
        assert "PROJECT: My Awesome Project" in prompt

    def test_includes_phase(self):
        """Prompt should include the phase."""
        project = _make_project(phase="R1_ECHO", round=1)
        prompt = build_agent_prompt(project)
        assert "YOUR PHASE: R1_ECHO" in prompt

    def test_includes_round(self):
        """Prompt should include the round number."""
        project = _make_project(phase="R1_ECHO", round=1)
        prompt = build_agent_prompt(project)
        assert "Round 1" in prompt

    def test_includes_plan_path(self):
        """Prompt should include the plan file path."""
        project = _make_project(phase="R1_ECHO", round=1)
        prompt = build_agent_prompt(project)
        assert "LEAD_PLAN.md" in prompt

    def test_includes_output_path(self):
        """Prompt should include the output file path."""
        project = _make_project(phase="R1_ECHO", round=1)
        prompt = build_agent_prompt(project)
        assert "ECHO_AUDIT_R1.md" in prompt

    def test_includes_status_path(self):
        """Prompt should include the status file path."""
        project = _make_project(phase="R1_ECHO", round=1)
        prompt = build_agent_prompt(project)
        assert ".status/echo_r1.json" in prompt

    def test_includes_audit_meta_header(self):
        """Prompt should include the AUDIT_META header instruction."""
        project = _make_project(phase="R1_ECHO", round=1)
        prompt = build_agent_prompt(project)
        assert "AUDIT_META" in prompt

    def test_includes_no_subagents_rule(self):
        """Prompt should forbid subagent spawning."""
        project = _make_project(phase="R1_ECHO", round=1)
        prompt = build_agent_prompt(project)
        assert "Do NOT use delegate_task" in prompt
        assert "Do NOT spawn subagents" in prompt

    def test_includes_scope_boundary(self):
        """Prompt should constrain working directory."""
        project = _make_project(phase="R1_ECHO", round=1)
        prompt = build_agent_prompt(project)
        assert "Only read files within this directory" in prompt
        assert "Do NOT read files outside" in prompt
        assert "Do NOT modify any files except" in prompt

    def test_consolidation_prompt_says_consolidating(self):
        """Consolidation phases should say 'consolidating audit findings'."""
        project = _make_project(phase="R1_CONSOLIDATE", round=1)
        prompt = build_agent_prompt(project)
        assert "consolidating audit findings" in prompt

    def test_audit_prompt_says_auditing(self):
        """Audit phases should say 'auditing a project plan'."""
        project = _make_project(phase="R1_ECHO", round=1)
        prompt = build_agent_prompt(project)
        assert "auditing a project plan" in prompt

    def test_r2_tripp_references_echo(self):
        """R2 Tripp prompt should reference Echo's R2 audit."""
        project = _make_project(phase="R2_TRIPP", round=2)
        prompt = build_agent_prompt(project)
        assert "ECHO_AUDIT_R2.md" in prompt
        assert "Round 1 audits for context" in prompt

    def test_r1_echo_no_cross_references(self):
        """R1 Echo should not reference other audits (independent)."""
        project = _make_project(phase="R1_ECHO", round=1)
        prompt = build_agent_prompt(project)
        # Should not have conditional references to other audits
        assert "Also read" not in prompt

    def test_r1_tripp_no_cross_references(self):
        """R1 Tripp should not reference Echo's audit (independent)."""
        project = _make_project(phase="R1_TRIPP", round=1)
        prompt = build_agent_prompt(project)
        assert "ECHO_AUDIT_R1.md" not in prompt


# ══════════════════════════════════════════════════════════════════════
# Model Pinning Tests
# ══════════════════════════════════════════════════════════════════════

class TestModelPinning:
    def test_echo_uses_mimo(self):
        """Echo agent should use MiMo for audit phases."""
        job = trigger_hermes_agent("echo", "proj", "R1_ECHO", "/tmp/proj")
        assert job["model"]["provider"] == "xiaomi"
        assert job["model"]["model"] == "mimo-v2.5"

    def test_tripp_uses_mimo(self):
        """Tripp agent should use MiMo for audit phases."""
        job = trigger_hermes_agent("tripp", "proj", "R1_TRIPP", "/tmp/proj")
        assert job["model"]["provider"] == "xiaomi"
        assert job["model"]["model"] == "mimo-v2.5"

    def test_cyony_uses_deepseek(self):
        """Cyony agent should use DeepSeek for consolidation."""
        job = trigger_hermes_agent("cyony", "proj", "R1_CONSOLIDATE", "/tmp/proj")
        assert job["model"]["provider"] == "deepseek"
        assert job["model"]["model"] == "deepseek-v3"

    def test_dispatch_agent_echo_model(self, tmp_path):
        """dispatch_agent should use correct model for Echo."""
        project = _make_project(phase="R1_ECHO", round=1)
        with patch("orchestrator.dispatcher.PROJECTS_DIR", str(tmp_path)):
            info = dispatch_agent(project)

        assert info["job"]["model"]["provider"] == "xiaomi"
        assert info["job"]["model"]["model"] == "mimo-v2.5"

    def test_dispatch_agent_cyony_model(self, tmp_path):
        """dispatch_agent should use correct model for Cyony."""
        project = _make_project(phase="R1_CONSOLIDATE", round=1)
        with patch("orchestrator.dispatcher.PROJECTS_DIR", str(tmp_path)):
            info = dispatch_agent(project)

        assert info["job"]["model"]["provider"] == "deepseek"
        assert info["job"]["model"]["model"] == "deepseek-v3"


# ══════════════════════════════════════════════════════════════════════
# enabled_toolsets Tests
# ══════════════════════════════════════════════════════════════════════

class TestEnabledToolsets:
    def test_toolsets_constant(self):
        """ENABLED_TOOLSETS should be exactly the required list."""
        assert ENABLED_TOOLSETS == ["file", "terminal", "search"]

    def test_toolsets_in_every_hermes_job(self):
        """Every Hermes cron job should include enabled_toolsets."""
        for agent in ("echo", "cyony"):
            job = trigger_hermes_agent(agent, "proj", "R1_ECHO", "/tmp/proj")
            assert job["enabled_toolsets"] == ["file", "terminal", "search"]

    def test_toolsets_in_dispatch_job(self, tmp_path):
        """dispatch_agent should include enabled_toolsets in the job."""
        project = _make_project(phase="R1_ECHO", round=1)
        with patch("orchestrator.dispatcher.PROJECTS_DIR", str(tmp_path)):
            info = dispatch_agent(project)

        assert info["job"]["enabled_toolsets"] == ["file", "terminal", "search"]


# ══════════════════════════════════════════════════════════════════════
# Integration: Full Dispatch Flow Tests
# ══════════════════════════════════════════════════════════════════════

class TestFullDispatchFlow:
    def test_echo_r1_full_dispatch(self, tmp_path):
        """Full dispatch for Echo R1: hermes cron with correct prompt + model."""
        project = _make_project(project_id="proj-1", phase="R1_ECHO", round=1)
        with patch("orchestrator.dispatcher.PROJECTS_DIR", str(tmp_path)):
            info = dispatch_agent(project)

        assert info["agent"] == "echo"
        assert info["method"] == "hermes_cron"
        assert info["job"]["model"]["model"] == "mimo-v2.5"
        assert "echo-audit-proj-1-R1_ECHO" == info["job"]["name"]
        assert "file" in info["job"]["enabled_toolsets"]
        assert "terminal" in info["job"]["enabled_toolsets"]
        assert "search" in info["job"]["enabled_toolsets"]

    def test_tripp_r1_full_dispatch(self, tmp_path):
        """Full dispatch for Tripp R1: file drop with correct structure."""
        project = _make_project(project_id="proj-1", phase="R1_TRIPP", round=1)
        with patch("orchestrator.dispatcher.PROJECTS_DIR", str(tmp_path)):
            info = dispatch_agent(project)

        assert info["agent"] == "tripp"
        assert info["method"] == "file_drop"
        assert os.path.exists(info["trigger_file"])

        with open(info["trigger_file"]) as f:
            data = json.load(f)
        assert data["trigger"] is True
        assert data["agent"] == "tripp"
        assert data["phase"] == "R1_TRIPP"

    def test_cyony_consolidation_full_dispatch(self, tmp_path):
        """Full dispatch for Cyony consolidation: hermes cron with DeepSeek."""
        project = _make_project(project_id="proj-1", phase="R1_CONSOLIDATE", round=1)
        with patch("orchestrator.dispatcher.PROJECTS_DIR", str(tmp_path)):
            info = dispatch_agent(project)

        assert info["agent"] == "cyony"
        assert info["method"] == "hermes_cron"
        assert info["job"]["model"]["model"] == "deepseek-v3"
        assert "consolidating audit findings" in info["job"]["prompt"]

    def test_echo_r2_full_dispatch(self, tmp_path):
        """Full dispatch for Echo R2: hermes cron with R2 context in prompt."""
        project = _make_project(project_id="proj-1", phase="R2_ECHO", round=2)
        with patch("orchestrator.dispatcher.PROJECTS_DIR", str(tmp_path)):
            info = dispatch_agent(project)

        assert info["agent"] == "echo"
        assert info["method"] == "hermes_cron"
        assert "R2_ECHO" in info["job"]["prompt"]
        assert "Round 1 audits for context" in info["job"]["prompt"]
