"""Tests for CrossDomainSynthesizer and interdisciplinary knowledge bridges."""

from pitagora.knowledge.synthesis import (
    CANONICAL_BRIDGES,
    CrossDomainSynthesizer,
    DomainConnection,
)


def test_canonical_bridges_exist():
    assert len(CANONICAL_BRIDGES) >= 5
    for b in CANONICAL_BRIDGES:
        assert b.source_concept
        assert b.target_concept
        assert b.relation_type
        assert len(b.description) > 10
        assert len(b.key_question) > 5


def test_find_connections():
    synth = CrossDomainSynthesizer()
    lagrange_conns = synth.find_connections("mech_lagrangian")
    assert len(lagrange_conns) >= 1
    assert any("metaphysics" in c.target_concept or "Action" in c.description for c in lagrange_conns)

    bayes_conns = synth.find_connections("prob_bayesian")
    assert len(bayes_conns) >= 1
    assert any("epistemology" in c.target_concept for c in bayes_conns)


def test_bridge_domains():
    synth = CrossDomainSynthesizer()
    conns = synth.bridge_domains("quantum", "philosophy")
    assert len(conns) >= 1
    assert conns[0].source_domain == "quantum"
    assert conns[0].target_domain == "philosophy"


def test_generate_synthesis_prompt():
    synth = CrossDomainSynthesizer()
    prompt = synth.generate_synthesis_prompt("mech_lagrangian", "mechanics")
    assert prompt["has_bridge"] is True
    assert prompt["target_domain"] == "philosophy"
    assert "socratic_question" in prompt

    # Fallback for unknown concept
    fallback = synth.generate_synthesis_prompt("custom_unseen_concept", "custom_domain")
    assert fallback["has_bridge"] is False
    assert fallback["target_domain"] == "philosophy"
    assert "custom_unseen_concept" in fallback["epistemic_context"]
