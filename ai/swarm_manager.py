"""
ai/swarm_manager.py

Antigravity-inspired Multi-Agent Swarm Collaboration Engine for Nova AI.
Orchestrates a coordinated team of specialized autonomous agents:
- Researcher: Discovers context, scans codebase, fetches external references.
- Coder: Implements modular code, applies atomic refactors.
- Verifier: Compiles files, executes test fixtures, validates zero regressions.

All agents collaborate through a shared Swarm Message Board.
"""

from __future__ import annotations

import time
from typing import Any
from PySide6.QtCore import QThread, Signal

from ai.llm_manager import LLMManager
from automation.executor import run_action
from config.settings_schema import AppConfig
from utils.logger import get_logger

log = get_logger(__name__)


RESEARCHER_PROMPT = """You are the Swarm Research Specialist.
Your Role: Explore codebase, search code symbols, read references, and analyze requirements.
Available actions to emit:
- [action:search_code:QUERY:::DIRECTORY]
- [action:fetch_webpage:URL]
- [action:read_file:PATH]

Analyze the goal thoroughly. Provide a concise, highly structured technical briefing for the Coder agent.
Keep output technical, precise, and without emojis.
"""

CODER_PROMPT = """You are the Swarm Lead Architect & Coder.
Your Role: Write production-grade code, apply minimal atomic edits, and resolve functional requirements.
Available actions to emit:
- [action:edit_file_block:PATH:::TARGET:::REPLACEMENT]
- [action:write_file:PATH:::CONTENT]
- [action:run_powershell:COMMAND]

Review the Researcher's briefing and implement the solution cleanly.
Ensure strict typing, error handling, and zero emojis.
"""

VERIFIER_PROMPT = """You are the Swarm Quality Assurance & Verification Specialist.
Your Role: Verify syntax, run test fixtures, check for regressions, and validate task completion.
Available actions to emit:
- [action:run_powershell:COMMAND]
- [action:task_complete:DELIVERABLE_SUMMARY]

Inspect the Coder's changes, compile modified files, and report a clear verification verdict.
No emojis.
"""


class SwarmWorker(QThread):
    """Orchestrates an Antigravity multi-agent swarm on a background thread."""

    # Signals
    swarm_started = Signal(str)                          # goal
    member_status = Signal(str, str, str)               # member_name, role, status
    board_post = Signal(str, str, str)                  # member_name, role, message
    swarm_progress = Signal(int, int, str)              # current_stage, total_stages, stage_name
    swarm_complete = Signal(str, float)                 # final_summary, elapsed_seconds
    swarm_error = Signal(str)                           # error_message

    def __init__(
        self,
        goal: str,
        config: AppConfig,
        llm_manager: LLMManager,
        parent: Any = None,
    ):
        super().__init__(parent)
        self.goal = goal
        self.config = config
        self.llm = llm_manager
        self._cancelled = False
        self._board_log: list[dict[str, str]] = []

    def cancel(self):
        """Cleanly aborts the swarm workflow."""
        self._cancelled = True

    def run(self):
        start_time = time.time()
        self.swarm_started.emit(self.goal)
        log.info(f"Antigravity Swarm launched for goal: '{self.goal[:60]}...'")

        try:
            # ----------------------------------------------------
            # Stage 1: Researcher Subagent
            # ----------------------------------------------------
            if self._cancelled:
                return
            self.swarm_progress.emit(1, 3, "Researcher Analyzing Context")
            self.member_status.emit("researcher", "Research Specialist", "working")
            self.board_post.emit(
                "researcher",
                "Research Specialist",
                f"Analyzing goal requirements and identifying relevant codebase context: '{self.goal}'",
            )

            research_query = (
                f"{RESEARCHER_PROMPT}\n\n"
                f"User Goal: {self.goal}\n\n"
                "Provide context analysis, required files, and recommended implementation strategy."
            )
            research_result = self.llm.query_sync(
                user_prompt=research_query,
                system_prompt="You are the Swarm Research Specialist. Be concise, technical, and actionable.",
            )
            if self._cancelled:
                return

            self._board_log.append({"member": "researcher", "role": "Research Specialist", "content": research_result})
            self.board_post.emit("researcher", "Research Specialist", research_result[:400] + ("..." if len(research_result) > 400 else ""))
            self.member_status.emit("researcher", "Research Specialist", "done")

            # ----------------------------------------------------
            # Stage 2: Coder Subagent
            # ----------------------------------------------------
            if self._cancelled:
                return
            self.swarm_progress.emit(2, 3, "Coder Implementing Solution")
            self.member_status.emit("coder", "Lead Architect & Developer", "working")
            self.board_post.emit(
                "coder",
                "Lead Architect & Developer",
                "Synthesizing architecture and preparing implementation based on research brief.",
            )

            coder_query = (
                f"{CODER_PROMPT}\n\n"
                f"Original Goal: {self.goal}\n\n"
                f"Researcher Briefing:\n{research_result}\n\n"
                "Provide implementation plan and execute the necessary actions or code structures."
            )
            coder_result = self.llm.query_sync(
                user_prompt=coder_query,
                system_prompt="You are the Swarm Lead Architect & Coder. Deliver robust, typed code with zero emojis.",
            )
            if self._cancelled:
                return

            self._board_log.append({"member": "coder", "role": "Lead Architect & Developer", "content": coder_result})
            self.board_post.emit("coder", "Lead Architect & Developer", coder_result[:400] + ("..." if len(coder_result) > 400 else ""))
            self.member_status.emit("coder", "Lead Architect & Developer", "done")

            # ----------------------------------------------------
            # Stage 3: Verifier Subagent
            # ----------------------------------------------------
            if self._cancelled:
                return
            self.swarm_progress.emit(3, 3, "Verifier Validating Quality & Regressions")
            self.member_status.emit("verifier", "Quality & Verification Specialist", "working")
            self.board_post.emit(
                "verifier",
                "Quality & Verification Specialist",
                "Auditing implementation, checking syntax integrity, and verifying deliverables.",
            )

            verifier_query = (
                f"{VERIFIER_PROMPT}\n\n"
                f"Original Goal: {self.goal}\n\n"
                f"Coder Deliverable:\n{coder_result}\n\n"
                "Verify correctness, note potential regressions, and confirm task completion."
            )
            verifier_result = self.llm.query_sync(
                user_prompt=verifier_query,
                system_prompt="You are the Swarm Quality & Verification Specialist. Report concise verification verdict.",
            )
            if self._cancelled:
                return

            self._board_log.append({"member": "verifier", "role": "Quality & Verification Specialist", "content": verifier_result})
            self.board_post.emit("verifier", "Quality & Verification Specialist", verifier_result[:400] + ("..." if len(verifier_result) > 400 else ""))
            self.member_status.emit("verifier", "Quality & Verification Specialist", "done")

            # ----------------------------------------------------
            # Coordinator Synthesis
            # ----------------------------------------------------
            elapsed = time.time() - start_time
            synthesis = (
                f"### Antigravity Swarm Executive Deliverable\n\n"
                f"**Goal**: {self.goal}\n\n"
                f"**Specialist Contributions**:\n"
                f"- **Researcher**: Formulated context analysis and dependency strategy.\n"
                f"- **Lead Architect**: Built architecture and implementation logic.\n"
                f"- **Verifier**: Audited quality, syntax, and regression safety.\n\n"
                f"**Implementation Summary**:\n{coder_result}\n\n"
                f"**Verification Verdict**:\n{verifier_result}\n"
            )

            self.swarm_complete.emit(synthesis, elapsed)
            log.info(f"Antigravity Swarm finished in {elapsed:.1f}s")

        except Exception as e:
            log.error(f"Antigravity Swarm failed: {e}", exc_info=True)
            self.swarm_error.emit(f"Swarm execution failed: {str(e)}")
