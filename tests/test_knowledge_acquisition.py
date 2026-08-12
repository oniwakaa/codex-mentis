import pytest
from unittest.mock import MagicMock, patch
from codex_mentis.knowledge.acquisition import KnowledgeAcquisition

def test_knowledge_acquisition_research_topic():
    # Setup mock KB and CG
    mock_kb = MagicMock()
    mock_cg = MagicMock()
    mock_cg.graph = {}
    
    acq = KnowledgeAcquisition(knowledge_base=mock_kb, concept_graph=mock_cg)
    
    # Mock Webfetch search and fetch responses
    mock_search = MagicMock(return_value=[
        {"title": "Quantum Mechanics", "url": "https://example.com/qm", "snippet": "Introduction to QM", "score": 0.9}
    ])
    mock_fetch = MagicMock(return_value={
        "title": "Quantum Mechanics", "text": "We define state space as Hilbert space. The wave function is defined as a complex function. Theorem: Normalization. $$P(x, t) = |\\Psi|^2$$", "url": "https://example.com/qm"
    })
    
    acq.webfetch.search = mock_search
    acq.webfetch.fetch_url = mock_fetch
    
    res = acq.research_topic("quantum mechanics", max_sources=1)
    
    assert res["topic"] == "quantum mechanics"
    assert res["total_sources_crawled"] == 1
    assert len(res["findings"]) > 0
    assert any("Hilbert space" in c for c in res["concepts_found"])
    
    # Verify KB was updated
    mock_kb.add_document.assert_called_once()
    # Verify CG was updated
    mock_cg.add_concept.assert_called()

def test_search_papers():
    acq = KnowledgeAcquisition()
    
    # Mock search calls
    mock_search = MagicMock(side_effect=[
        [{"title": "Paper 1", "url": "https://arxiv.org/abs/1"}], # arxiv search
        [{"title": "Paper 1", "url": "https://arxiv.org/abs/1"}, {"title": "Paper 2", "url": "https://arxiv.org/abs/2"}] # general search
    ])
    acq.webfetch.search = mock_search
    
    papers = acq.search_papers("quantum gravity", max_results=3)
    assert len(papers) == 2
    assert papers[0]["title"] == "Paper 1"
    assert papers[1]["title"] == "Paper 2"

def test_fetch_paper():
    acq = KnowledgeAcquisition()
    
    mock_fetch = MagicMock(return_value={
        "title": "Arxiv Paper Title",
        "text": "Abstract: We investigate quantum gravity. Introduction: Gravity is curvature.",
        "url": "https://arxiv.org/html/1"
    })
    acq.webfetch.fetch_url = mock_fetch
    
    paper_info = acq.fetch_paper("https://arxiv.org/abs/1")
    assert paper_info["title"] == "Arxiv Paper Title"
    assert "quantum gravity" in paper_info["abstract"].lower()
    assert paper_info["full_text_length"] > 0
    assert mock_fetch.call_args[0][0] == "https://arxiv.org/html/1" # converted abs to html

def test_extract_abstract_fallback():
    acq = KnowledgeAcquisition()
    text = "This is a paper about quantum cosmology."
    abstract = acq._extract_abstract(text)
    assert abstract == "This is a paper about quantum cosmology."
