import os
import sys
import datetime

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from pitagora.core.models import MemoryEntry, ReviewCard, ConceptMastery, SkillPerformance, CurriculumPlan, Skill as LegacySkill
from pitagora.memory.store import MemoryStore
from pitagora.memory.layers import ThreeLayerMemory
from pitagora.memory.retrieval import MemoryRetriever
from pitagora.memory.spaced_repetition import SpacedRepetition
from pitagora.concepts.graph import ConceptGraph
from pitagora.concepts.tracker import MasteryTracker
from pitagora.concepts.curriculum import CurriculumGenerator
from pitagora.skills.engine import SkillsEngine, Skill
from pitagora.skills.evolution import SkillEvolution

def test_all():
    print("--- STARTING NEW FEATURES VALIDATION ---")
    
    test_db = "/tmp/test_new_features.db"
    test_yaml = "/tmp/test_new_concepts.yaml"
    for path in [test_db, test_yaml]:
        if os.path.exists(path):
            os.remove(path)
            
    try:
        # 1. Concept Graph Enhancements
        print("\n[1] Testing ConceptGraph Enhancements...")
        graph = ConceptGraph(yaml_path=test_yaml)
        # Verify metadata
        algebra_details = graph.graph["Algebra"]
        print(f"Algebra metadata: difficulty={algebra_details['difficulty']}, time={algebra_details['estimated_learning_time']} mins")
        assert algebra_details["difficulty"] == 1
        
        # Verify bidirectional relationships
        print("Classical Mechanics dependents:", graph.get_dependents("Classical Mechanics"))
        print("Quantum Mechanics prerequisites:", graph.get_prerequisites("Quantum Mechanics"))
        assert "Quantum Mechanics" in graph.get_dependents("Classical Mechanics")
        
        # Verify clustering by domain
        clusters = graph.get_clusters_by_domain()
        print("Clusters:", list(clusters.keys()))
        assert "Mathematics" in clusters and "Physics" in clusters
        
        # Verify optimized path (build from easiest / prerequisites sorted)
        opt_path = graph.get_optimized_path("Quantum Mechanics", mastered_concepts=["Algebra"])
        print("Optimized path to QM (mastered Algebra):", opt_path)
        assert "Algebra" not in opt_path
        
        # Verify fuzzy matching / search
        search_res = graph.search_concepts("Schrodinger equation")
        print("Fuzzy search 'Schrodinger equation':", search_res)
        assert len(search_res) > 0 and search_res[0][0] == "Quantum Mechanics"
        
        # Verify exports
        json_path = "/tmp/test_graph.json"
        dot_path = "/tmp/test_graph.dot"
        graph.export_to_json(json_path)
        graph.export_to_dot(dot_path)
        assert os.path.exists(json_path) and os.path.exists(dot_path)
        print("Graph JSON/DOT exports successful.")
        
        # 2. Mastery Tracker Enhancements
        print("\n[2] Testing MasteryTracker Enhancements...")
        tracker = MasteryTracker(db_path=test_db, concept_graph=graph, decay_rate=0.1)
        # Update mastery
        tracker.update_mastery("Calculus", 0.9)
        raw_mastery = tracker.get_mastery("Calculus", apply_decay=False)
        decayed_mastery = tracker.get_mastery("Calculus", apply_decay=True)
        print(f"Calculus mastery: raw={raw_mastery:.4f}, decayed (freshly updated)={decayed_mastery:.4f}")
        assert abs(raw_mastery - decayed_mastery) < 1e-3
        
        # Verify progress report
        report = tracker.get_progress_report(domain="Mathematics")
        print("Progress Report (Math):", report)
        
        # Verify assessment generation
        assessment = tracker.generate_assessment("Calculus", num_questions=2)
        print("Generated Assessment for Calculus (2 questions):")
        for q in assessment["questions"]:
            print(f"  Q{q['id']} ({q['type']}): {q['question']}")
        assert len(assessment["questions"]) == 2
        
        # 3. Spaced Repetition Enhancements
        print("\n[3] Testing SpacedRepetition Enhancements...")
        sr = SpacedRepetition(db_path=test_db)
        # Check deck classification
        deck = sr.get_deck(graph)
        print(f"Deck statistics: new={len(deck['new'])}, learning={len(deck['learning'])}, review={len(deck['review'])}")
        assert "Algebra" in deck["new"]
        
        # Run double-linked updates
        sr.schedule_review("Algebra", 4, mastery_tracker=tracker)
        updated_algebra_mastery = tracker.get_mastery("Algebra")
        print(f"Updated Algebra mastery via spaced rep: {updated_algebra_mastery:.4f}")
        assert updated_algebra_mastery > 0.0
        
        # Performance analytics
        analytics = sr.get_performance_analytics()
        print("Performance Analytics:", analytics)
        assert analytics["total_cards"] > 0
        
        # 4. Memory Store Enhancements
        print("\n[4] Testing MemoryStore CRUD and Vector Search...")
        store = MemoryStore(db_path=test_db)
        
        # CRUD: Create
        entry = MemoryEntry(layer="L2", content="Newton's laws of motion form the basis of classical mechanics.", topic="Classical Mechanics")
        entry_id = store.create_memory_entry(entry)
        print(f"Created memory entry ID: {entry_id}")
        assert entry_id > 0
        
        # CRUD: Read
        retrieved_entry = store.get_memory_entry(entry_id)
        print(f"Read content: '{retrieved_entry.content}'")
        assert retrieved_entry.topic == "Classical Mechanics"
        
        # CRUD: Update
        retrieved_entry.content = "Newton's laws of motion: F = m*a."
        store.update_memory_entry(entry_id, retrieved_entry)
        updated_entry = store.get_memory_entry(entry_id)
        print(f"Updated content: '{updated_entry.content}'")
        assert "F = m*a" in updated_entry.content
        
        # CRUD: Delete
        store.delete_memory_entry(entry_id)
        assert store.get_memory_entry(entry_id) is None
        print("Deleted memory successfully.")
        
        # Backups and Exports
        backup_path = "/tmp/test_backup.db"
        export_path = "/tmp/test_export.json"
        assert store.backup_database(backup_path)
        assert store.export_memories(export_path)
        assert os.path.exists(backup_path) and os.path.exists(export_path)
        print("Database backup and memory export successful.")
        
        # 5. Hybrid Retrieval Search
        print("\n[5] Testing MemoryRetriever Hybrid Search...")
        retriever = MemoryRetriever(store)
        # Seed some data
        store.save(layer="L2", content="Lagrangian mechanics uses variational calculus to derive Euler-Lagrange equations.", topic="Classical Mechanics")
        store.save(layer="L2", content="Quantum mechanics governs the behavior of microscopic particles.", topic="Quantum Mechanics")
        
        # Search with hybrid score, topic boost, recency bias
        matches = retriever.search(query="Lagrangian mechanics", current_topic="Classical Mechanics")
        print("Hybrid search results:")
        for m in matches:
            print(f"  - [{m['topic']}] Score={m['score']:.4f} | {m['content']}")
        assert len(matches) > 0
        assert "Lagrangian" in matches[0]["content"]
        
        # 6. Adaptive Curriculum Generator
        print("\n[6] Testing Adaptive Curriculum Generator...")
        curriculum = CurriculumGenerator(concept_graph=graph, mastery_tracker=tracker, spaced_rep=sr)
        
        # Prerequisite Gap Analysis
        gap = curriculum.prerequisite_gap_analysis("Classical Mechanics")
        print("Gap Analysis for Classical Mechanics:")
        print(f"  Ready to study: {gap['is_ready_to_study']}")
        print(f"  Unmet prereqs: {[x['concept'] for x in gap['unmet_prerequisites']]}")
        
        # Milestones
        milestones = curriculum.get_milestones()
        print("Gateway milestones:")
        for m in milestones:
            print(f"  - Milestone: {m['milestone_concept']} | Completed: {m['completed']}")
            
        # Daily review schedule
        daily = curriculum.get_daily_review_schedule(max_reviews=3)
        print(f"Daily reviews count: {len(daily)}")
        
        # 7. Skills Engine
        print("\n[7] Testing Skills Engine Composition & Matches...")
        skills_dir = "/tmp/test_skills"
        skills_engine = SkillsEngine(skills_dir=skills_dir)
        
        # Save a new skill
        test_skill = Skill(
            name="EulerMethod",
            domain="Mathematics",
            description="Solving ordinary differential equations using Euler's method.",
            concepts=["Calculus"],
            common_mistakes=["Incorrect step size h selection"],
            verification_strategies=["Compare against analytical solution"],
            version=1
        )
        skills_engine.save_skill(test_skill)
        
        # Load skill
        loaded = skills_engine.load_skill("EulerMethod")
        print(f"Loaded skill: {loaded.name} | version: {loaded.version}")
        assert loaded.name == "EulerMethod"
        
        # Match skill
        matches = skills_engine.match_skills(topic="Calculus", problem_text="Solve ODE using steps")
        print(f"Matched skills for 'Calculus': {[s.name for s in matches]}")
        assert len(matches) > 0
        
        # Composite skill
        composite = skills_engine.create_composite_skill("CalculusSolver", ["eulermethod"])
        print(f"Composite skill '{composite.name}' domain: {composite.domain}")
        assert "CalculusSolver" in composite.name
        
        # 8. Skill Evolution: Thompson Sampling & A/B testing
        print("\n[8] Testing Skill Evolution (Thompson Sampling & A/B testing)...")
        evolution = SkillEvolution(db_path="/tmp/test_evolution_new.db")
        
        # Thompson sampling selection
        evolution.record_use("EulerMethod", success=True, feedback="Accurate step resolution", topic="Calculus")
        evolution.record_use("EulerMethod", success=False, feedback="Step h too large", topic="Calculus")
        selected = evolution.select_skill_thompson(["EulerMethod"])
        print(f"Thompson selected skill: {selected}")
        assert selected == "EulerMethod"
        
        # A/B testing variants
        variants = {
            "A": "Solve differential equation step-by-step.",
            "B": "Utilize Euler's forward difference formula to solve the ODE."
        }
        chosen_var, chosen_temp = evolution.select_prompt_variant("EulerMethod", variants)
        print(f"A/B test selected variant '{chosen_var}' template: '{chosen_temp}'")
        assert chosen_var in ("A", "B")
        
        # Record variant use
        evolution.record_use("EulerMethod", success=True, feedback="Good variant B response", topic="Calculus", variant="B")
        
        # Dashboard
        dashboard = evolution.get_performance_dashboard()
        print("Performance Dashboard:", dashboard)
        assert dashboard["total_usage_count"] > 0
        
    finally:
        # Cleanup temp files
        for f in [test_db, test_yaml, json_path, dot_path, backup_path, export_path, "/tmp/test_evolution_new.db"]:
            if os.path.exists(f):
                os.remove(f)
        import shutil
        if os.path.exists(skills_dir):
            shutil.rmtree(skills_dir)
            
    print("\n--- ALL NEW FEATURES VALIDATED SUCCESSFULLY! ---")

if __name__ == "__main__":
    test_all()
