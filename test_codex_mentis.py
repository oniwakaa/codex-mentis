import sys
import os

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

def run_tests():
    print("Starting Pitagora integration test...")
    print("=" * 60)

    # 1. Test Math Engine imports and basic operations
    print("\n[1/4] Testing Math Engine...")
    from pitagora.math_engine.sandbox import SymPySandbox
    from pitagora.math_engine.symbolic import SymbolicMath
    from pitagora.math_engine.numerical import NumericalMath
    from pitagora.math_engine.verification import MathVerifier
    from pitagora.math_engine.latex_render import LatexRenderer
    
    sandbox = SymPySandbox()
    res_eval = sandbox.evaluate("x**2 + 2*x + 1")
    print(f"Sandbox evaluation result: {res_eval.value} | latex: {res_eval.latex} | verified: {res_eval.verified}")
    assert res_eval.verified, "Sandbox evaluation failed"
    
    res_solve = sandbox.solve("x**2 - 4 = 0", "x")
    print(f"Sandbox solve result: {res_solve.value}")
    assert res_solve.verified, "Sandbox solve failed"

    symbolic = SymbolicMath(sandbox)
    res_prove = symbolic.prove_identity("(x-1)*(x+1)", "x**2 - 1", ["x"])
    print(f"Symbolic identity proof result: {res_prove.verified} | steps: {res_prove.steps}")
    assert res_prove.verified, "Symbolic proof failed"

    numerical = NumericalMath()
    res_num_eval = numerical.evaluate_float("pi", precision=5)
    print(f"Numerical evaluate float: {res_num_eval}")
    assert abs(res_num_eval - 3.14159) < 1e-3, "Numerical evaluation of pi failed"

    res_opt = numerical.optimize("x**2 - 4*x")
    print(f"Numerical optimization result: x = {res_opt.x} | min value = {res_opt.fun}")
    assert abs(res_opt.x - 2.0) < 1e-4, "Numerical optimization failed"

    verifier = MathVerifier(sandbox)
    res_verify = verifier.verify_claim("sin(x)**2 + cos(x)**2 = 1")
    print(f"Verifier claim check: {res_verify.verified} | confidence: {res_verify.confidence}")
    assert res_verify.verified, "Claim verification failed"

    renderer = LatexRenderer()
    inline_render = renderer.render_inline(r"\sum_{i=0}^n x_i^2")
    print(f"LaTeX inline render: {inline_render}")
    
    mat_render = renderer.render_matrix([[1, 2], [3, 4]])
    print(f"LaTeX matrix render:\n{mat_render}")

    # 2. Test Knowledge Base
    print("\n[2/4] Testing Knowledge Base...")
    from pitagora.knowledge.chunker import SmartChunker
    from pitagora.knowledge.embeddings import EmbeddingEngine
    from pitagora.knowledge.base import KnowledgeBase
    
    chunker = SmartChunker()
    test_text = """
# Physics Basics
This is the introduction.

Theorem: Force equals mass times acceleration.
$$F = m a$$
Proof: This is proven by Newton's second law.
QED
"""
    chunks = chunker.chunk(test_text, max_tokens=100)
    print(f"Smart Chunker chunks generated: {len(chunks)}")
    for idx, c in enumerate(chunks):
        print(f"  Chunk {idx+1}: section='{c.metadata.get('section')}' | has_eq={c.metadata.get('has_equation')}")
    assert len(chunks) > 0, "Chunking failed"

    embeddings = EmbeddingEngine(db_path="test_embeddings.db")
    v = embeddings.embed("Force equals mass times acceleration")
    print(f"Embedding generated vector size: {len(v)}")
    assert len(v) == 384, "Embedding vector size mismatch"

    kb = KnowledgeBase(db_path="test_kb.db", embedding_db_path="test_embeddings.db")
    kb.create("physics", "Physics collection")
    
    # Write a test markdown file to ingest
    test_md_path = os.path.join(PROJECT_ROOT, "test_document.md")
    with open(test_md_path, 'w', encoding='utf-8') as f:
        f.write(test_text)
        
    try:
        kb.add_document(test_md_path, "physics")
        search_res = kb.search("Newton's second law", "physics", top_k=2)
        print(f"KB Search result count: {len(search_res)}")
        for r in search_res:
            print(f"  Result score={r['score']:.4f} | text='{r['text'].strip()[:60]}...'")
        assert len(search_res) > 0, "KB search returned no results"
    finally:
        # Cleanup test document
        if os.path.exists(test_md_path):
            os.remove(test_md_path)
        # Cleanup test databases
        for db in ["test_kb.db", "test_embeddings.db"]:
            if os.path.exists(db):
                os.remove(db)

    # 3. Test Skills
    print("\n[3/4] Testing Skills Engine...")
    from pitagora.skills.engine import SkillsEngine
    from pitagora.skills.evolution import SkillEvolution
    
    engine = SkillsEngine()
    skills = engine.list_skills()
    print(f"List of skills found: {skills}")
    assert "algebra" in skills, "algebra skill not found in list"
    
    algebra_skill = engine.load_skill("algebra")
    print(f"Loaded skill: {algebra_skill.name} | domain: {algebra_skill.domain}")
    
    prompt = engine.get_prompt(algebra_skill, {"problem": "Solve x**2 - 5*x + 6 = 0"})
    print("Rendered Skill Prompt length:", len(prompt))
    assert len(prompt) > 100, "Prompt rendering failed"

    evolution = SkillEvolution(db_path="test_evolution.db")
    evolution.record_use("algebra", success=False, feedback="Failed to find negative roots", confidence=0.8)
    evolution.record_use("algebra", success=True, feedback="Found both roots successfully", confidence=0.9)
    stats = evolution.get_stats("algebra")
    print(f"Skill evolution stats: success_rate={stats.success_rate:.2f} | use_count={stats.use_count}")
    assert stats.use_count == 2, "Stats recording failed"
    
    evolved = evolution.evolve_prompt("algebra", "Base prompt template")
    print("Evolved prompt containing learned guidelines:")
    print(evolved)
    assert "Evolved Guidelines" in evolved, "Evolving prompt failed"
    
    # Cleanup test evolution database
    if os.path.exists("test_evolution.db"):
        os.remove("test_evolution.db")

    # 4. Test MCP Integrations
    print("\n[4/4] Testing MCP Integrations...")
    from pitagora.mcp_integration.evermemos import EverMemOSIntegration
    from pitagora.mcp_integration.obsidian import ObsidianIntegration
    from pitagora.mcp_integration.remarkable import RemarkableIntegration

    evermemos = EverMemOSIntegration(local_db_path="test_evermemos.db")
    evermemos.save_memory("Remember to study quantum mechanics", "physics")
    memos = evermemos.recall("quantum", ["physics"])
    print(f"EverMemOS recalled: {memos}")
    assert len(memos) > 0, "EverMemOS recall failed"
    
    briefing = evermemos.get_briefing("physics")
    print("EverMemOS Briefing:\n", briefing)

    obsidian = ObsidianIntegration(vault_dir="test_obsidian_vault")
    obsidian.write_note("Tensors", "Tensors are geometric objects...")
    note_content = obsidian.read_note("Tensors")
    print(f"Obsidian read note: {note_content}")
    assert "Tensors" in note_content, "Obsidian read note failed"
    
    search_obs = obsidian.search_notes("geometric")
    print(f"Obsidian search notes: {search_obs}")
    assert len(search_obs) > 0, "Obsidian search failed"
    
    obsidian.create_link("Tensors", "Manifolds")
    print(f"Obsidian created link, content now: {obsidian.read_note('Tensors')}")
    
    remarkable = RemarkableIntegration(cache_dir="test_remarkable_cache")
    docs = remarkable.list_documents()
    print(f"Remarkable docs: {docs}")
    
    # Clean up test directories
    import shutil
    for d in ["test_obsidian_vault", "test_remarkable_cache"]:
        if os.path.exists(d):
            shutil.rmtree(d)
    if os.path.exists("test_evermemos.db"):
        os.remove("test_evermemos.db")

    print("\n" + "=" * 60)
    print("All tests passed successfully!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
