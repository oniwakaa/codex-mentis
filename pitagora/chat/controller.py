"""Orchestration logic for ChatController."""

from __future__ import annotations

import logging
from collections.abc import Iterator

from pitagora import chat as chat_runtime
from pitagora.chat.renderer import ChatRenderer
from pitagora.chat.session import ChatEvent, ChatSessionState
from pitagora.teaching.analyzer import ResponseAnalyzer
from pitagora.teaching.session import TeachingSession, TeachingState

log = logging.getLogger(__name__)


class ChatController(ChatSessionState):
    """Headless conversation controller orchestrating turns and commands."""

    COMMANDS = {
        "/mode": "_cmd_mode",
        "/topic": "_cmd_topic",
        "/model": "_cmd_model",
        "/explore": "_cmd_explore",
        "/verify": "_cmd_verify",
        "/research": "_cmd_research",
        "/save": "_cmd_save",
        "/sessions": "_cmd_sessions",
        "/resume": "_cmd_resume",
        "/quiz": "_cmd_quiz",
        "/progress": "_cmd_progress",
        "/ingest": "_cmd_ingest",
        "/journeys": "_cmd_journeys",
        "/dashboard": "_cmd_dashboard",
        "/workflow": "_cmd_workflow",
        "/latex": "_cmd_latex",
        "/plot": "_cmd_plot",
        "/learn": "_cmd_learn",
        "/proactive": "_cmd_learn",
        "/rate": "_cmd_rate",
        "/help": "_cmd_help",
        "/clear": "_cmd_clear",
        "/quit": "_cmd_quit",
        "/exit": "_cmd_quit",
        "/q": "_cmd_quit",
    }

    def handle_input(self, user_input: str) -> Iterator[ChatEvent]:
        """Dispatch a line of user input to the appropriate handler."""
        text = user_input.strip()
        if not text:
            return
        if text.startswith("/"):
            yield from self._handle_command(text)
            return
        if self.teaching_session is not None:
            yield from self._handle_teaching_turn(text)
            return
        yield from self._handle_freeform_turn(user_input)

    def _handle_freeform_turn(self, user_input: str) -> Iterator[ChatEvent]:
        yield ChatEvent("user", user_input)
        rag_context = self.rag_lookup(user_input) if self.rag_lookup else ""
        concept_context = self.concept_lookup(self.topic) if self.concept_lookup else ""
        memory_context = (
            self.memory_lookup(user_input, self.topic)
            if getattr(self, "memory_lookup", None)
            else ""
        )
        contexts = [value for value in (rag_context, concept_context, memory_context) if value]
        enriched = (
            "\n\n".join(contexts) + f"\n\nUser question: {user_input}" if contexts else user_input
        )
        self.messages.append({"role": "user", "content": enriched})
        yield ChatEvent("status", "Thinking...", {"busy": True})
        try:
            from pitagora.agents.tools import ALL_AGENT_TOOLS

            try:
                raw_response = self.completion(
                    self.messages,
                    model=self.model,
                    config=self.config,
                    tools=ALL_AGENT_TOOLS,
                )
            except TypeError:
                raw_response = self.completion(
                    self.messages,
                    model=self.model,
                    config=self.config,
                )
        except Exception:
            self.messages.pop()
            raise

        response_text = ""
        tool_calls = []
        if isinstance(raw_response, dict):
            response_text = raw_response.get("content", "")
            tool_calls = raw_response.get("tool_calls", [])
        else:
            response_text = str(raw_response)

        # Handle structured tool calls if emitted
        for tc in tool_calls:
            func = tc.get("function", {}) if "function" in tc else tc
            name = func.get("name", "")
            args = func.get("arguments", {})
            if isinstance(args, str):
                import json
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            if name == "render_terminal_plot" and isinstance(args, dict):
                yield ChatEvent("plot", args)

        self.messages.append({"role": "assistant", "content": response_text})
        yield ChatEvent("markdown", response_text)
        verification = self.verify_math(response_text)
        if verification:
            yield ChatEvent("status", verification, {"verification": True})
        self.save_memory("user", user_input, topic=self.topic)
        self.save_memory("assistant", response_text, topic=self.topic)
        self.record_study(self.topic, user_input)
        self.message_count += 1
        self.last_freeform = {"topic": self.topic, "strategy": "socratic"}
        yield ChatEvent("state_changed", metadata={"context": self.context})

    def _handle_command(self, text: str) -> Iterator[ChatEvent]:
        command, _, argument = text.partition(" ")
        command = command.lower()
        handler_name = self.COMMANDS.get(command)
        if handler_name is None:
            yield ChatEvent("error", f"Unknown: {command}. /help for commands.")
            return
        yield from getattr(self, handler_name)(argument.strip())

    # ─── Delegated Commands ───

    def _cmd_mode(self, argument: str) -> Iterator[ChatEvent]:
        yield from self.cmd_mode(argument)

    def _cmd_topic(self, argument: str) -> Iterator[ChatEvent]:
        yield from self.cmd_topic(argument)

    def _cmd_model(self, argument: str) -> Iterator[ChatEvent]:
        yield from self.cmd_model(argument)

    def _cmd_clear(self, argument: str) -> Iterator[ChatEvent]:
        yield from self.cmd_clear(argument)

    def _cmd_save(self, argument: str) -> Iterator[ChatEvent]:
        yield from self.cmd_save(argument)

    def _cmd_sessions(self, argument: str) -> Iterator[ChatEvent]:
        yield from self.cmd_sessions(argument)

    def _cmd_resume(self, argument: str) -> Iterator[ChatEvent]:
        yield from self.cmd_resume(argument)

    def _cmd_quit(self, argument: str) -> Iterator[ChatEvent]:
        try:
            from pitagora.sessions import save_session

            if len(self.messages) > 1:
                save_session(self.messages, topic=self.topic, mode=self.mode)
        except Exception:
            pass
        yield ChatEvent("status", "Goodbye!", metadata={"quit": True})


    def _cmd_latex(self, argument: str) -> Iterator[ChatEvent]:
        yield from ChatRenderer.cmd_latex(argument)

    def _cmd_plot(self, argument: str) -> Iterator[ChatEvent]:
        yield from ChatRenderer.cmd_plot(argument)

    def _cmd_learn(self, argument: str) -> Iterator[ChatEvent]:
        yield from ChatRenderer.cmd_learn(self, argument)

    def _cmd_help(self, argument: str) -> Iterator[ChatEvent]:
        yield from ChatRenderer.cmd_help(argument)

    def _cmd_rate(self, argument: str) -> Iterator[ChatEvent]:
        yield from ChatRenderer.cmd_rate(self, argument)

    def _cmd_verify(self, argument: str) -> Iterator[ChatEvent]:
        yield from ChatRenderer.cmd_verify(argument)

    def _cmd_research(self, argument: str) -> Iterator[ChatEvent]:
        yield from ChatRenderer.cmd_research(argument)

    def _cmd_progress(self, argument: str) -> Iterator[ChatEvent]:
        yield from ChatRenderer.cmd_progress(self.topic, argument)

    def _cmd_ingest(self, argument: str) -> Iterator[ChatEvent]:
        yield from ChatRenderer.cmd_ingest(self.topic, argument)

    def _cmd_journeys(self, argument: str) -> Iterator[ChatEvent]:
        yield from ChatRenderer.cmd_journeys(argument)

    def _cmd_dashboard(self, argument: str) -> Iterator[ChatEvent]:
        yield from ChatRenderer.cmd_dashboard(argument)

    def _cmd_quiz(self, argument: str) -> Iterator[ChatEvent]:
        yield from ChatRenderer.cmd_quiz(self, argument)

    def _cmd_workflow(self, argument: str) -> Iterator[ChatEvent]:
        yield from ChatRenderer.cmd_workflow(self, argument)

    def _cmd_explore(self, argument: str) -> Iterator[ChatEvent]:
        arg = argument.strip()
        if arg == "--continue":
            yield from self._resume_journey()
            return
        if not arg:
            yield ChatEvent(
                "status",
                "Usage: /explore <topic>  (or /explore --continue)",
            )
            return
        yield from self._start_teaching(arg)

    def _start_teaching(self, topic: str) -> Iterator[ChatEvent]:
        yield ChatEvent("status", "Designing learning path...", {"busy": True})
        subs = chat_runtime._generate_sub_concepts(topic, self.config, self.model)
        session = TeachingSession(
            topic=topic,
            sub_concepts=subs,
            user_level="intermediate",
        )
        chat_runtime._seed_session_style(session, self.feedback_improver)
        session.transition(TeachingState.exploring)
        self.teaching_session = session
        self.teaching_analyzer = ResponseAnalyzer(self.completion)
        self.topic = topic

        try:
            from pitagora.journeys.store import get_or_create_journey

            journey = get_or_create_journey(topic, subs)
            journey.session_state = session.to_dict()
            self.teaching_journey = journey
        except Exception:
            self.teaching_journey = None

        yield ChatEvent(
            "renderable",
            {
                "topic": topic,
                "sub_concepts": subs,
                "level": session.user_level,
            },
        )
        yield from self._run_teaching_turn_events("begin")

    def _resume_journey(self) -> Iterator[ChatEvent]:
        try:
            from pitagora.journeys.store import list_journeys, load_journey

            journeys = [j for j in list_journeys() if j.get("status") in ("active", "paused")]
            if not journeys:
                yield ChatEvent(
                    "status",
                    "No journeys to continue. Use /explore <topic>.",
                )
                return
            journey = load_journey(journeys[0]["id"])
            if journey is None:
                yield ChatEvent("error", "Failed to load journey.")
                return
            session = TeachingSession.from_dict(journey.session_state)
            self.teaching_session = session
            self.teaching_analyzer = ResponseAnalyzer(self.completion)
            self.topic = session.topic
            self.teaching_journey = journey
            yield ChatEvent(
                "status",
                f"✓ Resumed journey '{journey.topic}' "
                f"({session.interaction_count} interactions)",
            )
            yield ChatEvent(
                "comprehension",
                session.comprehension_score,
            )
            yield ChatEvent("controls")
            yield ChatEvent("state_changed", metadata={"context": self.context})
        except Exception as e:
            yield ChatEvent("error", f"Resume failed: {e}")

    def _run_teaching_turn_events(self, user_input: str) -> Iterator[ChatEvent]:
        session = self.teaching_session
        analyzer = self.teaching_analyzer
        sc = session.current_subconcept
        sc_name = sc.name if sc else session.topic

        result = analyzer.classify(
            user_input,
            session.topic,
            sc_name,
            config=self.config,
            model=self.model,
        )
        session.apply_classification(
            result.label,
            result.delta,
            style=session.current_style,
        )

        if self.feedback_improver is not None:
            try:
                from pitagora.agents.self_improver import quality_from_classification

                self.feedback_improver.record_interaction(
                    topic=session.topic,
                    level=session.user_level,
                    strategy_used=session.current_style,
                    response_quality=quality_from_classification(result.label),
                    success=result.delta > 0,
                )
            except Exception as e:
                log.debug("feedback loop record_interaction failed: %s", e)

        if (
            self.feedback_skill_evo is not None
            and self.feedback_skills_engine is not None
            and user_input != "begin"
        ):
            try:
                matched = self.feedback_skills_engine.match_skills(
                    session.topic,
                    user_input,
                )
                if matched:
                    self.feedback_skill_evo.record_use(
                        matched[0].name,
                        success=result.delta > 0,
                        feedback=result.label,
                        topic=session.topic,
                    )
            except Exception as e:
                log.debug("skill usage record failed: %s", e)

        action = session.next_action(result.label)
        style = (
            session.style_effectiveness.best()
            if any(session.style_effectiveness.attempts.values())
            else session.current_style
        )
        session.current_style = style

        if action == "adapt":
            session.transition(TeachingState.adapting)
        elif action == "check":
            session.transition(TeachingState.checking)
        elif action == "visualize":
            session.transition(TeachingState.visualizing)
        elif action == "quiz":
            session.transition(TeachingState.quizzing)
        elif action == "review":
            session.transition(TeachingState.reviewing)
        elif action == "complete":
            session.complete()

        prompt = chat_runtime._build_teaching_prompt(session, action, style)
        self.messages.append({"role": "user", "content": prompt})
        yield ChatEvent("status", "Teaching...", {"busy": True})
        try:
            from pitagora.agents.tools import ALL_AGENT_TOOLS

            try:
                raw_response = self.completion(
                    self.messages,
                    model=self.model,
                    config=self.config,
                    tools=ALL_AGENT_TOOLS,
                )
            except TypeError:
                raw_response = self.completion(
                    self.messages,
                    model=self.model,
                    config=self.config,
                )
        except Exception:
            self.messages.pop()
            raise

        response_text = ""
        tool_calls = []
        if isinstance(raw_response, dict):
            response_text = raw_response.get("content", "")
            tool_calls = raw_response.get("tool_calls", [])
        else:
            response_text = str(raw_response)

        for tc in tool_calls:
            func = tc.get("function", {}) if "function" in tc else tc
            name = func.get("name", "")
            args = func.get("arguments", {})
            if isinstance(args, str):
                import json
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            if name == "render_terminal_plot" and isinstance(args, dict):
                yield ChatEvent("plot", args)

        self.messages.append({"role": "assistant", "content": response_text})

        yield ChatEvent("markdown", response_text)
        yield ChatEvent("comprehension", session.comprehension_score)
        yield ChatEvent(
            "subconcepts",
            [item.to_dict() for item in session.sub_concepts],
            {"current_index": session.current_index},
        )
        yield ChatEvent("controls")

        if self.teaching_journey is not None:
            try:
                from pitagora.journeys.store import save_journey

                self.teaching_journey.session_state = session.to_dict()
                self.teaching_journey.comprehension_history.append(
                    session.comprehension_score,
                )
                self.teaching_journey.sub_concepts = [sc.to_dict() for sc in session.sub_concepts]
                self.teaching_journey.interaction_count = session.interaction_count
                save_journey(self.teaching_journey)
            except Exception:
                pass

        yield ChatEvent("state_changed", metadata={"context": self.context})

    def _handle_teaching_turn(self, text: str) -> Iterator[ChatEvent]:
        session = self.teaching_session
        if text.strip().lower() == "p":
            session.pause()
            if self.teaching_journey is not None:
                try:
                    from pitagora.journeys.store import save_journey

                    self.teaching_journey.session_state = session.to_dict()
                    save_journey(self.teaching_journey)
                except Exception:
                    pass
            yield ChatEvent(
                "status",
                "Teaching paused. Resumable with /explore --continue. " "Back to free-form chat.",
            )
            self.teaching_session = None
            self.teaching_analyzer = None
            yield ChatEvent("state_changed", metadata={"context": self.context})
            return

        yield from self._run_teaching_turn_events(text)

        if (
            self.teaching_session is not None
            and self.teaching_session.state == TeachingState.completed
        ):
            session = self.teaching_session
            mastered = [sc.name for sc in session.sub_concepts if sc.mastery >= 0.8]
            yield ChatEvent(
                "renderable",
                {
                    "summary": True,
                    "topic": session.topic,
                    "comprehension": session.comprehension_score,
                    "interaction_count": session.interaction_count,
                    "best_style": session.style_effectiveness.best(),
                    "mastered": mastered,
                },
            )
            self.teaching_session = None
            self.teaching_analyzer = None
            yield ChatEvent("state_changed", metadata={"context": self.context})
