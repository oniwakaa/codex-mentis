import asyncio
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from pitagora.agents.base import BaseAgent, AgentResponse
from pitagora.agents.providers.base import BaseProvider

logger = logging.getLogger(__name__)

class DebateSynthesis(BaseModel):
    verdict: str = Field(description="The verdict of the debate: 'FOR', 'AGAINST', or 'UNDECIDED'")
    confidence: float = Field(description="Confidence in the verdict from 0.0 to 1.0")
    strongest_arguments_pro: List[str] = Field(description="The strongest arguments presented by the PRO side (Prover)")
    strongest_arguments_con: List[str] = Field(description="The strongest arguments presented by the CON side (Reviewer)")
    synthesis_summary: str = Field(description="A comprehensive analysis and summary of the debate, reconciling both sides")

class DebateAgent(BaseAgent):
    def __init__(self, provider: BaseProvider):
        super().__init__(
            name="DebateAgent",
            role="Structured Debate Facilitator and Synthesizer",
            provider=provider,
            system_prompt=(
                "You are the Debate Agent for Pitagora. Your role is to manage, moderate, "
                "and synthesize formal debates between two opposing mathematical/scientific positions."
            )
        )

    async def run_debate(
        self, 
        statement: str, 
        prover: BaseAgent, 
        reviewer: BaseAgent,
        synthesizer: Optional[BaseAgent] = None
    ) -> Dict[str, Any]:
        """
        Manages a structured formal debate on a statement between the Prover (FOR) and Reviewer (AGAINST).
        """
        synth_agent = synthesizer or self
        transcript: List[Dict[str, str]] = []

        logger.info(f"Starting structured debate on statement: '{statement}'")

        # =====================================================================
        # Round 1: Opening statements
        # =====================================================================
        logger.info("Debate Round 1: Opening Statements")
        pro_opening_prompt = (
            f"You are the Prover (Position A: FOR). Provide a rigorous opening statement "
            f"supporting the following statement: '{statement}'. Establish your core axioms and derivations."
        )
        con_opening_prompt = (
            f"You are the Reviewer (Position B: AGAINST). Provide a rigorous opening statement "
            f"opposing the following statement: '{statement}'. Highlight key concerns, definitions, and limitations."
        )

        # Run concurrently
        pro_opening_task = prover.athink(pro_opening_prompt)
        con_opening_task = reviewer.athink(con_opening_prompt)
        pro_opening, con_opening = await asyncio.gather(pro_opening_task, con_opening_task)

        transcript.append({"round": "1. Opening Statements", "agent": "Prover (FOR)", "content": pro_opening.content})
        transcript.append({"round": "1. Opening Statements", "agent": "Reviewer (AGAINST)", "content": con_opening.content})

        # =====================================================================
        # Round 2: Cross-examination
        # =====================================================================
        logger.info("Debate Round 2: Cross-examination")
        # Reviewer questions Prover's opening
        con_cross_prompt = (
            f"You are the Reviewer (Position B: AGAINST). Formally cross-examine and critique the Prover's opening statement. "
            f"Ask specific, pointed mathematical or physical questions highlighting potential flaws, sign errors, or loose logic in their argument.\n\n"
            f"Prover's Opening:\n{pro_opening.content}"
        )
        con_cross = await reviewer.athink(con_cross_prompt)
        transcript.append({"round": "2. Cross-examination", "agent": "Reviewer (AGAINST) to Prover", "content": con_cross.content})

        # Prover answers Reviewer's cross-examination
        pro_response_prompt = (
            f"You are the Prover (Position A: FOR). Respond to the Reviewer's cross-examination critique. "
            f"Clarify your steps, address their questions, and defend your opening statement against their specific points.\n\n"
            f"Reviewer's Critique:\n{con_cross.content}"
        )
        pro_response = await prover.athink(pro_response_prompt)
        transcript.append({"round": "2. Cross-examination", "agent": "Prover (FOR) response", "content": pro_response.content})

        # Prover questions Reviewer's opening
        pro_cross_prompt = (
            f"You are the Prover (Position A: FOR). Formally cross-examine and critique the Reviewer's opening statement. "
            f"Identify errors in their counter-examples, gaps in their logic, or misunderstandings of standard theory.\n\n"
            f"Reviewer's Opening:\n{con_opening.content}"
        )
        pro_cross = await prover.athink(pro_cross_prompt)
        transcript.append({"round": "2. Cross-examination", "agent": "Prover (FOR) to Reviewer", "content": pro_cross.content})

        # Reviewer answers Prover's cross-examination
        con_response_prompt = (
            f"You are the Reviewer (Position B: AGAINST). Respond to the Prover's cross-examination critique. "
            f"Defend your counter-position and address their criticisms directly.\n\n"
            f"Prover's Critique:\n{pro_cross.content}"
        )
        con_response = await reviewer.athink(con_response_prompt)
        transcript.append({"round": "2. Cross-examination", "agent": "Reviewer (AGAINST) response", "content": con_response.content})

        # =====================================================================
        # Round 3: Rebuttal
        # =====================================================================
        logger.info("Debate Round 3: Rebuttal")
        pro_rebuttal_prompt = (
            f"You are the Prover (Position A: FOR). Review the debate transcript so far, especially the Reviewer's answers. "
            f"Provide a definitive rebuttal, proving why the Reviewer's objections fail and why the statement '{statement}' holds.\n\n"
            f"Reviewer's Latest Response:\n{con_response.content}"
        )
        con_rebuttal_prompt = (
            f"You are the Reviewer (Position B: AGAINST). Review the debate transcript so far. "
            f"Provide a definitive rebuttal, demonstrating why the Prover's defense fails to save their derivation or statement: '{statement}'.\n\n"
            f"Prover's Latest Response:\n{pro_response.content}"
        )

        pro_rebuttal_task = prover.athink(pro_rebuttal_prompt)
        con_rebuttal_task = reviewer.athink(con_rebuttal_prompt)
        pro_rebuttal, con_rebuttal = await asyncio.gather(pro_rebuttal_task, con_rebuttal_task)

        transcript.append({"round": "3. Rebuttal", "agent": "Prover (FOR)", "content": pro_rebuttal.content})
        transcript.append({"round": "3. Rebuttal", "agent": "Reviewer (AGAINST)", "content": con_rebuttal.content})

        # =====================================================================
        # Round 4: Closing statements
        # =====================================================================
        logger.info("Debate Round 4: Closing Statements")
        pro_closing_prompt = (
            f"You are the Prover (Position A: FOR). Write a concise, powerful closing statement "
            f"summarizing your proof and arguments for: '{statement}'."
        )
        con_closing_prompt = (
            f"You are the Reviewer (Position B: AGAINST). Write a concise, powerful closing statement "
            f"summarizing your critiques and arguments against: '{statement}'."
        )

        pro_closing_task = prover.athink(pro_closing_prompt)
        con_closing_task = reviewer.athink(con_closing_prompt)
        pro_closing, con_closing = await asyncio.gather(pro_closing_task, con_closing_task)

        transcript.append({"round": "4. Closing Statements", "agent": "Prover (FOR)", "content": pro_closing.content})
        transcript.append({"round": "4. Closing Statements", "agent": "Reviewer (AGAINST)", "content": con_closing.content})

        # =====================================================================
        # Round 5: Synthesis
        # =====================================================================
        logger.info("Debate Round 5: Synthesis and Verdict")
        
        # Build raw transcript text for the synthesizer
        raw_transcript_str = ""
        for item in transcript:
            raw_transcript_str += f"[{item['round']}] {item['agent']}:\n{item['content']}\n\n"

        synthesis_prompt = (
            f"You are the Synthesizer. Review the following complete debate transcript between the Prover (FOR) "
            f"and Reviewer (AGAINST) on the statement: '{statement}'.\n\n"
            f"--- DEBATE TRANSCRIPT ---\n{raw_transcript_str}\n"
            f"Evaluate both sides objectively. Identify the strongest arguments for both FOR and AGAINST, "
            f"determine which side presented the mathematically/physically sounder argument, and output your verdict (FOR, AGAINST, or UNDECIDED) with confidence."
        )

        try:
            synthesis: DebateSynthesis = await synth_agent.athink_structured(synthesis_prompt, DebateSynthesis)
        except (ValueError, Exception) as e:
            logger.warning(f"Debate synthesis failed: {e}")
            synthesis = DebateSynthesis(
                verdict="UNDECIDED",
                confidence=0.0,
                strongest_arguments_pro=[],
                strongest_arguments_con=[],
                synthesis_summary=f"Synthesis failed: {e}",
            )

        return {
            "statement": statement,
            "transcript": transcript,
            "verdict": synthesis.verdict,
            "confidence": synthesis.confidence,
            "strongest_arguments_pro": synthesis.strongest_arguments_pro,
            "strongest_arguments_con": synthesis.strongest_arguments_con,
            "synthesis_summary": synthesis.synthesis_summary
        }
