def test_pain_listener_grades_explicit_buyer_pain_above_launch_proxy():
    from ode.heuristics.pain_listener import format_pain_report, listen

    signals = [
        {
            "source_id": "reddit_hot_rss",
            "source": "reddit/r/SaaS",
            "title": "Looking for an AI agent to stop manually reconciling invoices, would pay for this",
            "url": "https://example.com/reddit",
        },
        {
            "source_id": "producthunt_feed",
            "source": "producthunt",
            "title": "InvoicePilot",
            "summary": "AI workflow automation for invoice operations",
            "url": "https://example.com/ph",
            "rank": 2,
        },
    ]

    result = listen(signals, keywords=["AI agent", "automation"], min_grade="E")
    top = result["top_signals"][0]

    assert result["status"] == "ok"
    assert top["source_id"] == "reddit_hot_rss"
    assert top["evidence_grade"] in {"C", "D"}
    assert top["founder_fit"] >= 60
    assert result["validation_queues"]
    assert "Pain Listener Report" in format_pain_report(result)


def test_pain_listener_can_filter_to_direct_pain_evidence():
    from ode.heuristics.pain_listener import listen

    signals = [
        {
            "source_id": "producthunt_feed",
            "source": "producthunt",
            "title": "BuildDeck",
            "summary": "Beautiful pitch decks for founders",
            "rank": 1,
        },
        {
            "source_id": "hackernews_topstories",
            "source": "hackernews",
            "title": "Ask HN: Any tool for debugging LLM agent failures? This is blocking production",
            "score": 140,
            "comments": 64,
        },
    ]

    result = listen(signals, keywords=["LLM agent", "developer tools"], min_grade="D")

    assert result["kept_signals"] == 1
    assert result["top_signals"][0]["source_id"] == "hackernews_topstories"
    assert result["top_signals"][0]["evidence_grade"] in {"C", "D"}


def test_product_hunt_launches_are_capped_as_solution_side_evidence():
    from ode.heuristics.pain_listener import listen

    signals = [
        {
            "source_id": "producthunt_feed",
            "source": "producthunt",
            "title": "DebugFlow",
            "summary": "Stop painful manual debugging for AI agents, paid teams use it",
            "rank": 1,
        },
    ]

    result = listen(signals, keywords=["AI agents", "developer tools"], min_grade="E")

    assert result["top_signals"][0]["source_id"] == "producthunt_feed"
    assert result["top_signals"][0]["evidence_grade"] == "D"
    assert result["top_signals"][0]["recommendation"] == "Map To Pain"


def test_success_stories_do_not_upgrade_into_pain_signals():
    from ode.heuristics.pain_listener import listen

    signals = [
        {
            "source_id": "reddit_hot_rss",
            "source": "reddit/r/SaaS",
            "title": "I just made my first internet money ever and I couldn't be happier",
            "summary": "People pay for my subscription script, and I solved a problem.",
            "url": "https://example.com/story",
        },
        {
            "source_id": "reddit_hot_rss",
            "source": "reddit/r/SaaS",
            "title": "Looking for a tool to automate invoice follow ups, would pay for this",
            "url": "https://example.com/pain",
        },
    ]

    result = listen(signals, keywords=["automation", "SaaS"], min_grade="E")

    assert result["kept_signals"] == 1
    assert result["top_signals"][0]["url"] == "https://example.com/pain"
    assert "first internet money" not in result["top_signals"][0]["title"]
