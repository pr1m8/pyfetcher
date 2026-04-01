r"""Robots.txt parser for :mod:`pyfetcher`.

Purpose:
    Parse ``robots.txt`` files and check URL access permissions for a given
    user-agent. Supports ``Allow``, ``Disallow``, ``Crawl-delay``, and
    ``Sitemap`` directives.

Examples:
    ::

        >>> txt = "User-agent: *\\nDisallow: /admin"
        >>> rules = parse_robots_txt(txt)
        >>> is_allowed(rules, "/admin", user_agent="*")
        False
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RobotsRules:
    """Parsed robots.txt rules.

    Args:
        rules: Mapping of user-agent patterns to lists of (allow, path) tuples.
        sitemaps: List of sitemap URLs found in the robots.txt.
        crawl_delays: Mapping of user-agent patterns to crawl delay seconds.

    Examples:
        ::

            >>> rules = RobotsRules()
            >>> rules.sitemaps
            []
    """

    rules: dict[str, list[tuple[bool, str]]] = field(default_factory=dict)
    sitemaps: list[str] = field(default_factory=list)
    crawl_delays: dict[str, float] = field(default_factory=dict)


def parse_robots_txt(content: str) -> RobotsRules:
    r"""Parse a robots.txt file content.

    Extracts ``User-agent``, ``Allow``, ``Disallow``, ``Crawl-delay``,
    and ``Sitemap`` directives into a structured :class:`RobotsRules`
    object.

    Args:
        content: The raw text content of a robots.txt file.

    Returns:
        A :class:`RobotsRules` object containing parsed directives.

    Examples:
        ::

            >>> txt = "User-agent: *\\nDisallow: /secret\\nAllow: /public"
            >>> rules = parse_robots_txt(txt)
            >>> len(rules.rules.get("*", []))
            2
    """
    result = RobotsRules()
    current_agents: list[str] = []

    for raw_line in content.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue

        if ":" not in line:
            continue

        directive, _, value = line.partition(":")
        directive = directive.strip().lower()
        value = value.strip()

        if directive == "user-agent":
            current_agents = [value.lower()]
            for agent in current_agents:
                if agent not in result.rules:
                    result.rules[agent] = []
        elif directive == "disallow" and current_agents:
            for agent in current_agents:
                if agent not in result.rules:
                    result.rules[agent] = []
                if value:
                    result.rules[agent].append((False, value))
        elif directive == "allow" and current_agents:
            for agent in current_agents:
                if agent not in result.rules:
                    result.rules[agent] = []
                result.rules[agent].append((True, value))
        elif directive == "crawl-delay" and current_agents:
            try:
                delay = float(value)
                for agent in current_agents:
                    result.crawl_delays[agent] = delay
            except ValueError:
                pass
        elif directive == "sitemap":
            result.sitemaps.append(value)

    return result


def is_allowed(
    rules: RobotsRules,
    path: str,
    *,
    user_agent: str = "*",
) -> bool:
    r"""Check if a path is allowed for the given user-agent.

    Evaluates the parsed robots.txt rules for the most specific matching
    user-agent. ``Allow`` directives take precedence over ``Disallow``
    when paths have equal specificity (longer path prefix wins).

    Args:
        rules: Parsed robots.txt rules from :func:`parse_robots_txt`.
        path: The URL path to check (e.g. ``'/admin/settings'``).
        user_agent: The user-agent string to check against. Defaults to
            ``'*'`` (wildcard).

    Returns:
        ``True`` if the path is allowed, ``False`` if disallowed.

    Examples:
        ::

            >>> txt = "User-agent: *\\nDisallow: /admin\\nAllow: /admin/public"
            >>> rules = parse_robots_txt(txt)
            >>> is_allowed(rules, "/admin/settings")
            False
            >>> is_allowed(rules, "/admin/public")
            True
    """
    agent_key = user_agent.lower()

    agent_rules = rules.rules.get(agent_key) or rules.rules.get("*", [])

    if not agent_rules:
        return True

    best_match: tuple[bool, int] | None = None

    for allowed, rule_path in agent_rules:
        if path.startswith(rule_path) or rule_path == "":
            specificity = len(rule_path)
            if best_match is None or specificity > best_match[1]:
                best_match = (allowed, specificity)
            elif specificity == best_match[1] and allowed:
                best_match = (allowed, specificity)

    if best_match is None:
        return True

    return best_match[0]
