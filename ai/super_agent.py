"""
ai/super_agent.py

Autonomous Base44-grade Super Agent Engine for Nova AI.
Features:
- Continuous ReAct Loop (Reasoning -> Action -> Observation -> Self-Correction).
- Executes multi-step developer, system admin, and web automation tasks autonomously.
- Automatically diagnoses errors (syntax, runtime, missing dependencies) and iterates until done.
- Multi-threaded background worker with real-time UI signals.
"""

from __future__ import annotations

import re
import time
from typing import Callable

from PySide6.QtCore import QThread, Signal

from ai.llm_manager import ChatMessage, LLMManager
from automation import executor as automation_executor
from config.settings_schema import AppConfig
from utils.logger import get_logger

log = get_logger(__name__)

SUPER_AGENT_SYSTEM_PROMPT = """You are NOVA SUPERAGENT — an autonomous Base44-grade AI system administrator, software architect, and digital execution engine.
You operate in a continuous autonomous loop: (Thought -> Action -> Observation -> Next Thought -> Next Action).

WORKSPACE ROOT: E:\\Nova_AI

AVAILABLE AUTONOMOUS TOOLS:
- [action:run_command:COMMAND] - Run PowerShell, batch, python, git, pip, or pytest commands.
- [action:read_file:PATH] - Read local files, scripts, logs, or configs.
- [action:create_file:PATH:CONTENT] - Write a full file (syntax checked).
- [action:edit_file_block:PATH:::TARGET:::REPLACEMENT] - Search and replace an exact block of code.
- [action:search_code:QUERY:::DIRECTORY] - Search keywords inside files across workspace.
- [action:list_dir:PATH] - List directory files.
- [action:web_search:QUERY] - Perform live web search.
- [action:fetch_webpage:URL] - Fetch webpage text content.
- [action:update_focus:CONCISE_ACTIVITY] - Broadcast live high-level focus headline to HUD.
- [action:update_steps:STEP1 (done)|STEP2 (in_progress)|STEP3 (pending)] - Broadcast dynamic step checklist.
- [action:system_stats] - Win32 CPU, RAM, and Disk metrics.
- [action:task_complete:EXECUTIVE_SUMMARY] - CALL THIS WHEN GOAL IS FULLY SATISFIED AND VERIFIED!

RULES OF AUTONOMOUS OPERATION:
1. Always state a concise 'Thought:' explaining your rationale before taking action.
2. Output one or more [action:NAME:ARG] tags.
3. If an action fails (e.g. error, missing file, test failure), diagnose why, fix the code/environment, and retry!
4. Do not ask the user for permission on routine steps — you are fully empowered to complete the goal.
5. Once your verification confirms the objective is met, call [action:task_complete:detailed deliverable summary]!
"""


class SuperAgentWorker(QThread):
    iteration_started = Signal(int, str)             # (iteration, thought)
    action_started = Signal(int, str, str)          # (iteration, action_name, arg)
    action_completed = Signal(int, str, bool, str)  # (iteration, action_name, success, output)
    agent_finished = Signal(bool, str, int, float)   # (all_ok, final_summary, total_steps, elapsed_sec)

    def __init__(
        self,
        goal: str,
        config: AppConfig,
        llm_manager: LLMManager,
        max_iterations: int = 8,
    ):
        super().__init__()
        self.goal = goal.strip()
        self.config = config
        self.llm_manager = llm_manager
        self.max_iterations = max_iterations
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        t0 = time.time()
        log.info("SuperAgent started goal: {}", self.goal)

        history: list[ChatMessage] = [
            ChatMessage(
                role="user",
                content=(
                    f"OBJECTIVE: {self.goal}\n\n"
                    f"Begin autonomous execution. Plan your first step, take action, and iterate until the objective is completely accomplished."
                ),
            )
        ]

        total_actions_run = 0
        final_summary = ""
        success = True

        for iteration in range(1, self.max_iterations + 1):
            if self._is_cancelled:
                self.agent_finished.emit(False, "SuperAgent loop cancelled by user.", total_actions_run, time.time() - t0)
                return

            log.info("SuperAgent iteration {}/{}", iteration, self.max_iterations)

            # Query LLM
            try:
                reply = self.llm_manager.chat_sync(
                    messages=history,
                    system_prompt=SUPER_AGENT_SYSTEM_PROMPT,
                    temperature=0.2,
                )
            except Exception as e:
                err_msg = f"LLM Inference error during iteration {iteration}: {e}"
                log.error(err_msg)
                self.agent_finished.emit(False, err_msg, total_actions_run, time.time() - t0)
                return

            # Extract thought & action tags
            clean_text, action_tags = automation_executor.extract_actions(reply)

            # Extract thought text
            thought_match = re.search(r"(?:Thought|Thinking):\s*(.*?)(?=\[action:|\n\n|$)", reply, re.IGNORECASE | re.DOTALL)
            thought = thought_match.group(1).strip() if thought_match else clean_text.splitlines()[0] if clean_text else "Analyzing workspace and planning execution..."
            self.iteration_started.emit(iteration, thought[:120])

            # Record assistant turn in context
            history.append(ChatMessage(role="assistant", content=reply))

            # Check if task is declared complete
            complete_tag = next((arg for name, arg in action_tags if name in ("task_complete", "goal_achieved", "agent_finish")), None)
            if complete_tag:
                final_summary = complete_tag if complete_tag.strip() else clean_text
                log.info("SuperAgent completed goal on iteration {}", iteration)
                break

            if not action_tags:
                # If no actions were emitted and no complete tag, prompt LLM to proceed
                history.append(
                    ChatMessage(
                        role="user",
                        content="No action tags detected. Please formulate your next step and emit [action:NAME:ARG], or if finished, emit [action:task_complete:SUMMARY].",
                    )
                )
                continue

            # Execute all emitted action tags
            observations = []
            for act_name, act_arg in action_tags:
                if self._is_cancelled:
                    self.agent_finished.emit(False, "SuperAgent stopped by user.", total_actions_run, time.time() - t0)
                    return

                total_actions_run += 1
                self.action_started.emit(iteration, act_name, act_arg[:80])

                try:
                    ok, output = automation_executor.run_action(act_name, act_arg)
                except Exception as exc:
                    ok, output = False, f"Action execution exception: {exc}"

                self.action_completed.emit(iteration, act_name, ok, output[:120])
                status_str = "SUCCESS" if ok else "FAILED"
                observations.append(f"[{status_str}] Tool [{act_name}]:\n{output}")

            # Feed observations back to LLM for next thought iteration
            obs_feedback = "\n\n".join(observations)
            feedback_prompt = (
                f"OBSERVATION REPORT (Iteration {iteration}/{self.max_iterations}):\n"
                f"{obs_feedback}\n\n"
                f"Analyze these results. If there are any errors or remaining steps, take corrective action. "
                f"If the objective is now completely achieved and verified, call [action:task_complete:Detailed Summary]."
            )
            history.append(ChatMessage(role="user", content=feedback_prompt))

        elapsed = time.time() - t0
        if not final_summary:
            final_summary = (
                f"SuperAgent completed {self.max_iterations} autonomous iterations ({total_actions_run} actions executed). "
                f"Review the execution log for detailed status."
            )

        self.agent_finished.emit(success, final_summary, total_actions_run, elapsed)
