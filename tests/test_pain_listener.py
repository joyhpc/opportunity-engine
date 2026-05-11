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


def test_show_hn_how_to_launch_story_is_downranked():
    from ode.heuristics.pain_listener import analyze_signal

    signal = analyze_signal({
        "source_id": "hackernews_topstories",
        "source": "hackernews",
        "title": "Show HN: How to scale your SaaS to 1M ARR",
        "summary": "I built and launched my SaaS and want to share lessons.",
        "score": 300,
        "comments": 100,
    })

    assert "show hn" in signal.downrank_markers
    assert "how to" not in signal.pain_markers
    assert signal.evidence_grade == "E"
    assert signal.recommendation == "Watch"


def test_show_hn_question_launch_story_is_downranked():
    from ode.heuristics.pain_listener import analyze_signal

    signal = analyze_signal({
        "source_id": "hackernews_topstories",
        "source": "hackernews",
        "title": "Show HN: My SaaS for invoice automation, what do you think?",
        "summary": "I launched this after building an internal workflow.",
        "score": 180,
        "comments": 80,
    })

    assert "show hn" in signal.downrank_markers
    assert signal.evidence_grade == "E"
    assert signal.recommendation == "Watch"


def test_tutorial_titles_do_not_become_direct_pain_evidence():
    from ode.heuristics.pain_listener import analyze_signal, listen

    raw = {
        "source_id": "hackernews_topstories",
        "source": "hackernews",
        "title": "Best way to deploy Rails to AWS",
        "score": 250,
        "comments": 60,
    }

    signal = analyze_signal(raw)
    assert signal.pain_markers == []
    assert signal.request_markers == []
    assert signal.evidence_grade == "E"

    result = listen([raw], min_grade="D")
    assert result["kept_signals"] == 0


def test_request_without_buyer_urgency_or_pain_stays_weak():
    from ode.heuristics.pain_listener import analyze_signal

    signal = analyze_signal({
        "source_id": "hackernews_topstories",
        "source": "hackernews",
        "title": "Ask HN: Recommend a tool for organizing notes",
        "score": 210,
        "comments": 70,
    })

    assert "recommend" in signal.request_markers
    assert signal.pain_markers == []
    assert signal.evidence_grade == "E"


def test_invalid_pain_min_grade_is_explicit_error():
    from ode.heuristics.pain_listener import listen

    try:
        listen([], min_grade="A")
    except ValueError as exc:
        assert "Unsupported pain evidence grade" in str(exc)
    else:
        raise AssertionError("Expected invalid pain grade to raise ValueError")


def test_founder_fit_negative_terms_are_profile_driven():
    from ode.heuristics.pain_listener import analyze_signal

    raw = {
        "source_id": "reddit_hot_rss",
        "source": "reddit/r/SaaS",
        "title": "Need help with hardware manufacturing workflow automation",
        "summary": "Manual process is blocking production and we would pay for a fix.",
    }
    default_signal = analyze_signal(raw)
    hardware_friendly = analyze_signal(raw, profile={
        "negative_keywords": [],
        "soft_negative_keywords": [],
        "preferred_channels": ["reddit/r/saas"],
    })

    assert hardware_friendly.founder_fit > default_signal.founder_fit


def test_validation_queues_include_all_signal_tags():
    from ode.heuristics.pain_listener import listen

    result = listen([
        {
            "source_id": "reddit_hot_rss",
            "source": "reddit/r/SaaS",
            "title": "Need help with AI agent API debugging, would pay for a fix",
            "summary": "Manual workflow is blocking production for our developer team.",
        },
    ], keywords=["AI agents", "developer tools"], min_grade="E")

    themes = {queue["theme_key"] for queue in result["validation_queues"]}

    assert "ai_agents" in themes
    assert "developer_tools" in themes


def test_source_events_are_structured_and_rendered_in_empty_report():
    from ode.heuristics.pain_listener import format_pain_report, listen

    result = listen([], source_events=[{
        "source_id": "reddit_hot_rss",
        "status": "failed",
        "reason": "http_status",
        "http_status": 403,
        "subreddit": "SaaS",
    }])
    report = format_pain_report(result)

    assert result["source_events"][0]["http_status"] == 403
    assert "reddit_hot_rss did not return usable data" in result["source_notes"][-1]
    assert "## Source Events" in report
    assert "http=403" in report
