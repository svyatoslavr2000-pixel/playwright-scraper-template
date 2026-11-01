from scraper.politeness import origin_of, parse_robots, path_of

ROBOTS = """
User-agent: *
Disallow: /private/
Allow: /private/readme
Disallow: /*.pdf$
Crawl-delay: 2

User-agent: BadBot
Disallow: /
"""


def test_disallow_and_allow_longest_match_wins():
    policy = parse_robots(ROBOTS)
    assert policy.allowed("/catalog") is True
    assert policy.allowed("/private/secret") is False
    assert policy.allowed("/private/readme") is True  # longer Allow rule
    assert policy.allowed("/files/report.pdf") is False
    assert policy.allowed("/files/report.pdf?x=1") is True  # $ anchor


def test_wildcard_group_is_used_for_unknown_agent():
    policy = parse_robots(ROBOTS, agent="MyBot/1.0")
    assert policy.allowed("/catalog") is True
    assert policy.crawl_delay == 2.0


def test_exact_group_beats_wildcard():
    policy = parse_robots(ROBOTS, agent="badbot")
    assert policy.allowed("/catalog") is False
    assert policy.crawl_delay is None


def test_empty_disallow_means_everything_allowed():
    policy = parse_robots("User-agent: *\nDisallow:\n")
    assert policy.allowed("/anything") is True


def test_missing_robots_is_empty_policy():
    policy = parse_robots("")
    assert policy.is_empty
    assert policy.allowed("/x") is True


def test_url_helpers():
    assert origin_of("https://example.com/a?b=1") == "https://example.com"
    assert path_of("https://example.com/a?b=1") == "/a?b=1"
    assert path_of("https://example.com") == "/"
