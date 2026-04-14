"""
Generic GitHub API utilities.

Thin wrapper around PyGithub — all functions return plain dicts.
No candidate / sourcing logic here.

Other agents can use these for:
  - Verifying a candidate's GitHub activity           (A5)
  - Researching a company's open-source footprint     (A4)
  - Looking up repo contributors or tech stack        (A2)
  - Any general GitHub lookup                         (A6)

Requires GITHUB_TOKEN env var.
"""
from __future__ import annotations

import logging
import os

from github import Github, GithubException

logger = logging.getLogger(__name__)


def _get_client() -> Github | None:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        logger.warning("GITHUB_TOKEN not set — GitHub calls will fail.")
        return None
    return Github(token)


# ── Users ─────────────────────────────────────────────────────────────────────

def search_users(query: str, max_results: int = 30) -> list[dict]:
    """Search GitHub users by an arbitrary query string.

    Returns lightweight dicts (login + display name + URL).
    Use get_user_profile() to enrich individual results.

    Args:
        query:       Any GitHub user-search query
                     (e.g. 'python fastapi location:"San Francisco"').
        max_results: Maximum number of results to return.

    Returns:
        list of dicts with keys: login, name, github_url.
    """
    gh = _get_client()
    if not gh:
        return []

    results: list[dict] = []
    try:
        for user in gh.search_users(query):
            if len(results) >= max_results:
                break
            results.append({
                "login":      user.login,
                "name":       user.name or user.login,
                "github_url": user.html_url,
            })
    except GithubException as e:
        logger.error("GitHub search_users failed for %r: %s", query, e)
    return results


def get_user_profile(login: str) -> dict | None:
    """Fetch a full GitHub user profile by login.

    Args:
        login: GitHub username.

    Returns:
        dict with keys: login, name, email, location, bio, github_url,
        top_repos, languages, public_repos, followers, account_created_at (ISO str).
        Returns None if the user is not found.
    """
    gh = _get_client()
    if not gh:
        return None

    try:
        user = gh.get_user(login)
    except GithubException:
        return None

    try:
        repos = sorted(user.get_repos(), key=lambda r: r.stargazers_count, reverse=True)[:5]
        top_repos = [r.full_name for r in repos]
        languages  = list({r.language for r in repos if r.language})
    except GithubException:
        repos, top_repos, languages = [], [], []

    email = (
        user.email
        or _email_from_events(user)
        or _email_from_commits(repos, login)
    )

    created_at = None
    try:
        created_at = user.created_at.isoformat() if user.created_at else None
    except Exception:
        pass

    return {
        "login":              login,
        "name":               user.name or login,
        "email":              email,
        "location":           user.location or None,
        "bio":                user.bio or None,
        "github_url":         user.html_url,
        "top_repos":          top_repos,
        "languages":          languages,
        "public_repos":       user.public_repos,
        "followers":          user.followers,
        "account_created_at": created_at,
    }


def _email_from_events(user) -> str | None:
    """Extract a real email from the user's public push events.

    Push event payloads contain raw commit author emails that are often
    present even when the profile email is hidden.
    """
    try:
        for event in user.get_public_events():
            if event.type != "PushEvent":
                continue
            for commit in event.payload.get("commits", []):
                email = (commit.get("author") or {}).get("email", "")
                if email and "noreply" not in email and "@" in email:
                    return email
    except GithubException:
        pass
    return None


def _email_from_commits(repos: list, login: str) -> str | None:
    """Scan recent commits across the user's top repos for a real email."""
    for repo in repos[:5]:
        try:
            checked = 0
            for commit in repo.get_commits(author=login):
                for email in (
                    commit.commit.author.email or "",
                    commit.commit.committer.email or "",
                ):
                    if email and "noreply" not in email and "@" in email:
                        return email
                checked += 1
                if checked >= 5:
                    break
        except GithubException:
            continue
    return None


# ── Repos ─────────────────────────────────────────────────────────────────────

def search_repos(query: str, max_results: int = 10) -> list[dict]:
    """Search GitHub repositories by an arbitrary query string.

    Args:
        query:       Any GitHub repo-search query
                     (e.g. 'fastapi stars:>500 language:python').
        max_results: Maximum number of results to return.

    Returns:
        list of dicts with keys: full_name, description, language,
        stars, forks, url, topics.
    """
    gh = _get_client()
    if not gh:
        return []

    results: list[dict] = []
    try:
        for repo in gh.search_repositories(query):
            if len(results) >= max_results:
                break
            results.append({
                "full_name":   repo.full_name,
                "description": repo.description or None,
                "language":    repo.language or None,
                "stars":       repo.stargazers_count,
                "forks":       repo.forks_count,
                "url":         repo.html_url,
                "topics":      repo.get_topics(),
            })
    except GithubException as e:
        logger.error("GitHub search_repos failed for %r: %s", query, e)
    return results
