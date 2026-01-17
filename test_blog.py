"""
Unit tests for the private blog application.
Run with: pytest test_blog.py -v
"""

import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from main import (
    app,
    parse_frontmatter,
    get_posts,
    get_post,
    is_rate_limited,
    record_login_attempt,
    generate_csrf_token,
    login_attempts,
    BLOG_PASSWORD,
)


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_rate_limits():
    """Clear rate limiting state between tests."""
    login_attempts.clear()
    yield
    login_attempts.clear()


class TestFrontmatterParsing:
    """Tests for frontmatter parsing."""

    def test_parse_frontmatter_with_valid_frontmatter(self):
        content = """---
title: Test Post
date: 2025-01-17
---

This is the body content."""

        frontmatter, body = parse_frontmatter(content)

        assert frontmatter["title"] == "Test Post"
        assert frontmatter["date"] == "2025-01-17"
        assert body == "This is the body content."

    def test_parse_frontmatter_without_frontmatter(self):
        content = "Just plain content without frontmatter."

        frontmatter, body = parse_frontmatter(content)

        assert frontmatter == {}
        assert body == content

    def test_parse_frontmatter_with_empty_frontmatter(self):
        content = """---
---

Body content."""

        frontmatter, body = parse_frontmatter(content)

        assert frontmatter == {}
        assert body == "Body content."


class TestCSRFToken:
    """Tests for CSRF token generation."""

    def test_generate_csrf_token_returns_string(self):
        token = generate_csrf_token()
        assert isinstance(token, str)
        assert len(token) > 20  # Should be reasonably long

    def test_generate_csrf_token_unique(self):
        tokens = [generate_csrf_token() for _ in range(10)]
        assert len(set(tokens)) == 10  # All unique


class TestRateLimiting:
    """Tests for rate limiting functionality."""

    def test_is_rate_limited_false_initially(self):
        assert not is_rate_limited("192.168.1.1")

    def test_is_rate_limited_after_max_attempts(self):
        ip = "192.168.1.2"
        for _ in range(5):
            record_login_attempt(ip)

        assert is_rate_limited(ip)

    def test_is_rate_limited_different_ips_independent(self):
        ip1 = "192.168.1.3"
        ip2 = "192.168.1.4"

        for _ in range(5):
            record_login_attempt(ip1)

        assert is_rate_limited(ip1)
        assert not is_rate_limited(ip2)


class TestAuthentication:
    """Tests for authentication endpoints."""

    def test_home_redirects_when_not_authenticated(self, client):
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 303
        assert "/login" in response.headers["location"]

    def test_login_page_loads(self, client):
        response = client.get("/login")
        assert response.status_code == 200
        assert "Private Blog" in response.text
        assert "csrf_token" in response.text

    def test_login_without_csrf_fails(self, client):
        response = client.post(
            "/login",
            data={"password": BLOG_PASSWORD},
            follow_redirects=False
        )
        assert response.status_code == 422  # Validation error

    def test_login_with_wrong_csrf_fails(self, client):
        # Get login page to establish session
        client.get("/login")

        response = client.post(
            "/login",
            data={"password": BLOG_PASSWORD, "csrf_token": "invalid"},
            follow_redirects=False
        )
        assert response.status_code == 403

    def test_login_with_correct_credentials(self, client):
        # Get CSRF token
        login_page = client.get("/login")
        import re
        match = re.search(r'name="csrf_token"\s+value="([^"]+)"', login_page.text)
        csrf_token = match.group(1)

        response = client.post(
            "/login",
            data={"password": BLOG_PASSWORD, "csrf_token": csrf_token},
            follow_redirects=False
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/"

    def test_login_with_wrong_password(self, client):
        # Get CSRF token
        login_page = client.get("/login")
        import re
        match = re.search(r'name="csrf_token"\s+value="([^"]+)"', login_page.text)
        csrf_token = match.group(1)

        response = client.post(
            "/login",
            data={"password": "wrongpassword", "csrf_token": csrf_token},
        )
        assert "Invalid password" in response.text

    def test_logout_clears_session(self, client):
        # Login first
        login_page = client.get("/login")
        import re
        match = re.search(r'name="csrf_token"\s+value="([^"]+)"', login_page.text)
        csrf_token = match.group(1)

        client.post(
            "/login",
            data={"password": BLOG_PASSWORD, "csrf_token": csrf_token},
        )

        # Verify logged in
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 200

        # Logout
        client.get("/logout")

        # Verify logged out
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 303


class TestBlogPosts:
    """Tests for blog post functionality."""

    def test_get_posts_returns_list(self):
        posts = get_posts()
        assert isinstance(posts, list)

    def test_get_post_nonexistent_returns_none(self):
        post = get_post("nonexistent-post-slug")
        assert post is None

    def test_get_post_example_exists(self):
        post = get_post("example")
        assert post is not None
        assert post["slug"] == "example"
        assert "title" in post
        assert "content" in post

    def test_post_view_requires_auth(self, client):
        response = client.get("/post/example", follow_redirects=False)
        assert response.status_code == 303
        assert "/login" in response.headers["location"]

    def test_post_view_with_auth(self, client):
        # Login first
        login_page = client.get("/login")
        import re
        match = re.search(r'name="csrf_token"\s+value="([^"]+)"', login_page.text)
        csrf_token = match.group(1)

        client.post(
            "/login",
            data={"password": BLOG_PASSWORD, "csrf_token": csrf_token},
        )

        # View post
        response = client.get("/post/example")
        assert response.status_code == 200
        assert "Welcome" in response.text

    def test_post_404_for_nonexistent(self, client):
        # Login first
        login_page = client.get("/login")
        import re
        match = re.search(r'name="csrf_token"\s+value="([^"]+)"', login_page.text)
        csrf_token = match.group(1)

        client.post(
            "/login",
            data={"password": BLOG_PASSWORD, "csrf_token": csrf_token},
        )

        response = client.get("/post/nonexistent")
        assert response.status_code == 404


class TestAPIDocsDisabled:
    """Tests that API docs are disabled."""

    def test_docs_disabled(self, client):
        response = client.get("/docs")
        assert response.status_code == 404

    def test_redoc_disabled(self, client):
        response = client.get("/redoc")
        assert response.status_code == 404

    def test_openapi_disabled(self, client):
        response = client.get("/openapi.json")
        assert response.status_code == 404
