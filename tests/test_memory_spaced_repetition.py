import pytest
from datetime import date, timedelta
from pitagora.memory.spaced_repetition import SpacedRepetition

def test_spaced_repetition_sm2_reps(temp_db):
    sr = SpacedRepetition(db_path=temp_db)
    
    # 1. First review, perfect quality (5)
    d1 = sr.schedule_review("Calculus", 5)
    m1 = sr.get_review_metrics("Calculus")
    assert m1["repetitions"] == 1
    assert m1["interval"] == 1
    assert m1["ease_factor"] > 2.5
    assert d1 == date.today() + timedelta(days=1)
    
    # 2. Second review, quality 4
    d2 = sr.schedule_review("Calculus", 4)
    m2 = sr.get_review_metrics("Calculus")
    assert m2["repetitions"] == 2
    assert m2["interval"] == 6
    assert d2 == date.today() + timedelta(days=6)
    
    # 3. Third review, quality 5
    d3 = sr.schedule_review("Calculus", 5)
    m3 = sr.get_review_metrics("Calculus")
    assert m3["repetitions"] == 3
    # interval should be round(6 * ease_factor)
    assert m3["interval"] == int(round(6 * m2["ease_factor"]))
    
    # 4. Failure review, quality 2 (resets repetitions)
    d4 = sr.schedule_review("Calculus", 2)
    m4 = sr.get_review_metrics("Calculus")
    assert m4["repetitions"] == 0
    assert m4["interval"] == 1
    assert m4["ease_factor"] < m3["ease_factor"]

def test_spaced_repetition_due_and_deck(temp_db):
    sr = SpacedRepetition(db_path=temp_db)
    
    # Schedule a review today (due tomorrow)
    sr.schedule_review("Concept A", 4)
    
    # Schedule another review that is due today (let's insert it manually or review with quality < 3 which sets interval=1)
    # Wait, quality < 3 sets interval=1 (tomorrow). Let's mock or check if tomorrow works or modify next_review date in db if needed.
    # Actually, we can check due reviews. Since both are set to tomorrow, due today is 0.
    due = sr.get_due_reviews()
    assert len(due) == 0
    
    # Mock ConceptGraph
    class DummyGraph:
        graph = {
            "Concept A": {},
            "Concept B": {},
            "Concept C": {}
        }
    cg = DummyGraph()
    
    deck = sr.get_deck(cg)
    # Concept A has repetitions > 0 -> 'review'
    # Concept B & C are not in reviews -> 'new'
    assert "Concept A" in deck["review"]
    assert "Concept B" in deck["new"]
    assert "Concept C" in deck["new"]

def test_performance_analytics(temp_db):
    sr = SpacedRepetition(db_path=temp_db)
    sr.schedule_review("Concept A", 5)
    sr.schedule_review("Concept B", 2) # reps = 0 (learning)
    
    analytics = sr.get_performance_analytics()
    assert analytics["total_cards"] == 2
    assert analytics["learning_count"] == 1
    assert analytics["review_count"] == 1
    assert analytics["avg_ease_factor"] > 1.3
