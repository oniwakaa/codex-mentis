import os
import sys

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from pitagora.concepts.graph import ConceptGraph
from pitagora.concepts.tracker import MasteryTracker
from pitagora.concepts.curriculum import CurriculumGenerator
from pitagora.memory.store import MemoryStore
from pitagora.memory.layers import ThreeLayerMemory
from pitagora.memory.spaced_repetition import SpacedRepetition
from pitagora.agents.providers import ProviderConfig, get_provider
from pitagora.agents import TutorAgent, ResearchAgent, ProverAgent, ReviewerAgent, VisualizerAgent
from pitagora.agents.orchestrator import Orchestrator

def main():
    print("--- STARTING END-TO-END VALIDATION ---")
    
    # Use temporary locations for safety
    test_db = "/tmp/test_pitagora.db"
    test_yaml = "/tmp/test_concepts.yaml"
    if os.path.exists(test_db):
        os.remove(test_db)
    if os.path.exists(test_yaml):
        os.remove(test_yaml)
        
    try:
        # 1. Concept Graph Test
        print("\n[1] Testing ConceptGraph...")
        graph = ConceptGraph(yaml_path=test_yaml)
        print("Loaded graph concepts:", list(graph.graph.keys()))
        assert "Calculus" in graph.graph
        print("Prerequisites of Quantum Mechanics:", graph.get_prerequisites("Quantum Mechanics"))
        print("Learning path for Quantum Mechanics:", graph.get_learning_path("Quantum Mechanics"))
        print("ASCII Prerequisite Tree:\n" + graph.visualize("Quantum Mechanics"))
        
        # 2. Mastery Tracker Test
        print("\n[2] Testing MasteryTracker...")
        tracker = MasteryTracker(db_path=test_db, concept_graph=graph)
        print("Initial mastery score for Algebra:", tracker.get_mastery("Algebra"))
        tracker.update_mastery("Algebra", 0.9)
        tracker.update_mastery("Algebra", 0.95)
        print("Updated mastery score for Algebra (expecting > 0.8):", tracker.get_mastery("Algebra"))
        assert tracker.get_mastery("Algebra") > 0.8
        print("Strong areas:", tracker.get_strong_areas())
        
        # 3. Memory Store Test
        print("\n[3] Testing MemoryStore...")
        store = MemoryStore(db_path=test_db)
        store.save(layer="L2", content="Lagrangian mechanics uses L = T - V.", topic="Classical Mechanics")
        store.save(layer="L3", content="Integrals are the inverse operations of derivatives.", topic="Calculus")
        matches = store.retrieve("Lagrangian mechanics", top_k=2)
        print("Found semantic match:", matches[0]["content"], "Score:", matches[0]["score"])
        assert "Lagrangian" in matches[0]["content"]
        
        # 4. Spaced Repetition Test
        print("\n[4] Testing SpacedRepetition...")
        sr = SpacedRepetition(db_path=test_db)
        next_date = sr.schedule_review("Quantum Mechanics", 5) # quality 5
        print("Scheduled QM next review date:", next_date)
        metrics = sr.get_review_metrics("Quantum Mechanics")
        print("QM reps:", metrics["repetitions"], "interval:", metrics["interval"])
        assert metrics["repetitions"] == 1
        
        # 5. Curriculum Generator Test
        print("\n[5] Testing CurriculumGenerator...")
        curriculum = CurriculumGenerator(concept_graph=graph, mastery_tracker=tracker, spaced_rep=sr)
        suggestion = curriculum.suggest_next()
        print("Suggested next concept:", suggestion["concept"], "Reason:", suggestion["reason"])
        plan = curriculum.generate_study_plan("Quantum Mechanics")
        print("Study plan for QM:")
        for week_item in plan:
            print(f"  Week {week_item['week']}: {week_item['concept']}")
            
        # 6. Agents and Orchestrator Test
        print("\n[6] Testing Agents & Orchestrator initialization...")
        config = ProviderConfig(api_key="mock", model="mock-model", base_url="http://localhost:11434/v1")
        prov = get_provider("local", config)
        
        agents = {
            "tutor": TutorAgent(prov),
            "researcher": ResearchAgent(prov),
            "prover": ProverAgent(prov),
            "reviewer": ReviewerAgent(prov),
            "visualizer": VisualizerAgent(prov)
        }
        
        orchestrator = Orchestrator(agents=agents, memory=ThreeLayerMemory(store, prov), concept_graph=graph)
        print("Orchestrator successfully initialized with Tutor, Researcher, Prover, Reviewer, and Visualizer agents.")
        
        # 7. Visualizer Plot Test
        print("\n[7] Testing Visualizer expression plotter...")
        plot_output = agents["visualizer"].plot_expression("x**2", x_range=(-2, 2))
        print("Plot output (x**2 from -2 to 2):\n" + plot_output)
        
        print("\n--- ALL TESTS PASSED SUCCESSFULLY! ---")
        
    finally:
        # Clean up files
        if os.path.exists(test_db):
            os.remove(test_db)
        if os.path.exists(test_yaml):
            os.remove(test_yaml)

if __name__ == "__main__":
    main()
