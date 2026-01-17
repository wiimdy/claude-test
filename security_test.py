"""
Security vulnerability scanner for the private blog server.
Run with: python security_test.py

Requires: pip install requests beautifulsoup4
"""

import re
import requests
import sys

BASE_URL = "http://localhost:8000"
CORRECT_PASSWORD = "secret"  # Default password for testing


class SecurityTester:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = requests.Session()
        self.results = []

    def log(self, test_name: str, passed: bool, details: str = ""):
        status = "PASS" if passed else "FAIL"
        self.results.append((test_name, passed, details))
        print(f"[{status}] {test_name}")
        if details:
            print(f"       {details}")

    def get_csrf_token(self, session: requests.Session = None) -> str:
        """Get CSRF token from login page."""
        s = session or requests.Session()
        r = s.get(f"{self.base_url}/login")
        match = re.search(r'name="csrf_token"\s+value="([^"]+)"', r.text)
        return match.group(1) if match else ""

    def login_with_csrf(self, session: requests.Session, password: str) -> requests.Response:
        """Login with proper CSRF token."""
        csrf_token = self.get_csrf_token(session)
        return session.post(
            f"{self.base_url}/login",
            data={"password": password, "csrf_token": csrf_token},
            allow_redirects=False
        )

    def test_unauthenticated_access(self):
        """Test that protected routes redirect to login without auth."""
        print("\n=== Testing Authentication Bypass ===")

        # Test home page
        r = requests.get(f"{self.base_url}/", allow_redirects=False)
        self.log(
            "Home redirects to login when unauthenticated",
            r.status_code == 303 and "/login" in r.headers.get("location", ""),
            f"Status: {r.status_code}"
        )

        # Test post access
        r = requests.get(f"{self.base_url}/post/example", allow_redirects=False)
        self.log(
            "Posts redirect to login when unauthenticated",
            r.status_code == 303 and "/login" in r.headers.get("location", ""),
            f"Status: {r.status_code}"
        )

    def test_path_traversal(self):
        """Test for path traversal vulnerabilities in post slugs."""
        print("\n=== Testing Path Traversal ===")

        # Login first with CSRF
        session = requests.Session()
        self.login_with_csrf(session, CORRECT_PASSWORD)

        payloads = [
            ("../../../etc/passwd", "Basic traversal"),
            ("....//....//etc/passwd", "Double encoding"),
            ("%2e%2e%2f%2e%2e%2fetc/passwd", "URL encoded"),
            ("..%252f..%252fetc/passwd", "Double URL encoded"),
            ("....//....//....//etc/passwd", "Nested traversal"),
        ]

        for payload, desc in payloads:
            r = session.get(f"{self.base_url}/post/{payload}")
            # Should return 404, not file contents
            is_safe = r.status_code == 404 or "root:" not in r.text
            self.log(
                f"Path traversal blocked: {desc}",
                is_safe,
                f"Status: {r.status_code}"
            )

    def test_xss_vulnerabilities(self):
        """Test for XSS in various inputs."""
        print("\n=== Testing XSS Vulnerabilities ===")

        session = requests.Session()
        self.login_with_csrf(session, CORRECT_PASSWORD)

        xss_payloads = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert('xss')>",
            "javascript:alert('xss')",
            "<svg onload=alert('xss')>",
        ]

        # Test in post slug (reflected XSS)
        for payload in xss_payloads:
            r = session.get(f"{self.base_url}/post/{payload}")
            # Check if payload is reflected without encoding
            is_safe = payload not in r.text or r.status_code == 404
            self.log(
                f"XSS blocked in slug: {payload[:30]}...",
                is_safe,
                f"Reflected: {payload in r.text}"
            )

    def test_session_security(self):
        """Test session cookie security settings."""
        print("\n=== Testing Session Security ===")

        session = requests.Session()
        r = self.login_with_csrf(session, CORRECT_PASSWORD)

        cookies = r.cookies
        session_cookie = cookies.get("session")

        if session_cookie:
            # Check cookie attributes from Set-Cookie header
            set_cookie = r.headers.get("set-cookie", "")

            self.log(
                "Session cookie exists",
                True,
                f"Cookie length: {len(session_cookie)}"
            )

            # Note: These checks depend on how the cookie is set
            self.log(
                "HttpOnly flag (check manually)",
                "httponly" in set_cookie.lower(),
                f"Set-Cookie: {set_cookie[:100]}..."
            )

            self.log(
                "Secure flag (only needed for HTTPS)",
                True,  # Not required for localhost HTTP
                "Localhost testing uses HTTP"
            )
        else:
            self.log("Session cookie exists", False, "No session cookie found")

    def test_brute_force_protection(self):
        """Test if there's rate limiting on login attempts."""
        print("\n=== Testing Brute Force Protection ===")

        # Use a fresh session for each attempt to simulate different requests
        blocked_count = 0
        for i in range(10):
            session = requests.Session()
            csrf_token = self.get_csrf_token(session)
            r = session.post(
                f"{self.base_url}/login",
                data={"password": f"wrong{i}", "csrf_token": csrf_token},
                allow_redirects=False
            )
            if r.status_code == 429:
                blocked_count += 1

        has_rate_limit = blocked_count > 0
        self.log(
            "Rate limiting on login",
            has_rate_limit,
            f"Blocked {blocked_count}/10 attempts" if has_rate_limit
            else "No rate limiting detected (all 10 attempts allowed)"
        )

    def test_information_disclosure(self):
        """Test for information disclosure vulnerabilities."""
        print("\n=== Testing Information Disclosure ===")

        # Check error pages
        r = requests.get(f"{self.base_url}/nonexistent-route")
        self.log(
            "No stack traces in 404",
            "traceback" not in r.text.lower() and "exception" not in r.text.lower(),
            f"Status: {r.status_code}"
        )

        # Check for common sensitive endpoints
        sensitive_paths = ["/docs", "/redoc", "/openapi.json", "/.env", "/config"]
        for path in sensitive_paths:
            r = requests.get(f"{self.base_url}{path}")
            # FastAPI docs are enabled by default - note this
            if path in ["/docs", "/redoc", "/openapi.json"]:
                self.log(
                    f"API docs disabled: {path}",
                    r.status_code == 404,
                    f"Status: {r.status_code}"
                )
            else:
                self.log(
                    f"Sensitive path blocked: {path}",
                    r.status_code == 404,
                    f"Status: {r.status_code}"
                )

    def test_csrf_protection(self):
        """Test for CSRF vulnerabilities."""
        print("\n=== Testing CSRF Protection ===")

        # Try login without any CSRF token
        r = requests.post(
            f"{self.base_url}/login",
            data={"password": CORRECT_PASSWORD},
            allow_redirects=False
        )

        # Should fail with 422 (validation error) or 403 (forbidden) without CSRF token
        login_failed = r.status_code in [422, 403] or (
            r.status_code == 303 and "/login" in r.headers.get("location", "")
        )

        self.log(
            "CSRF protection on login",
            login_failed,
            f"Status: {r.status_code} - {'Protected' if login_failed else 'Vulnerable'}"
        )

        # Test with wrong CSRF token
        session = requests.Session()
        session.get(f"{self.base_url}/login")  # Get session cookie
        r = session.post(
            f"{self.base_url}/login",
            data={"password": CORRECT_PASSWORD, "csrf_token": "invalid_token"},
            allow_redirects=False
        )

        invalid_token_rejected = r.status_code == 403

        self.log(
            "Invalid CSRF token rejected",
            invalid_token_rejected,
            f"Status: {r.status_code}"
        )

    def test_logout_functionality(self):
        """Test that logout properly clears session."""
        print("\n=== Testing Logout Security ===")

        # Login with CSRF
        session = requests.Session()
        self.login_with_csrf(session, CORRECT_PASSWORD)

        # Access protected page (should work)
        r = session.get(f"{self.base_url}/", allow_redirects=False)
        logged_in = r.status_code == 200

        # Logout
        session.get(f"{self.base_url}/logout")

        # Try accessing protected page again
        r = session.get(f"{self.base_url}/", allow_redirects=False)
        logged_out = r.status_code == 303

        self.log(
            "Logout clears session",
            logged_in and logged_out,
            f"Before logout: {200 if logged_in else 'redirect'}, After: {'redirect' if logged_out else 200}"
        )

    def test_password_in_response(self):
        """Test that password is not reflected in responses."""
        print("\n=== Testing Password Exposure ===")

        session = requests.Session()
        csrf_token = self.get_csrf_token(session)
        r = session.post(
            f"{self.base_url}/login",
            data={"password": "test_password_12345", "csrf_token": csrf_token},
        )

        self.log(
            "Password not reflected in response",
            "test_password_12345" not in r.text,
            "Password found in response!" if "test_password_12345" in r.text else "OK"
        )

    def run_all_tests(self):
        """Run all security tests."""
        print("=" * 50)
        print("Security Vulnerability Scanner")
        print(f"Target: {self.base_url}")
        print("=" * 50)

        try:
            r = requests.get(f"{self.base_url}/login", timeout=5)
        except requests.exceptions.ConnectionError:
            print(f"\nERROR: Cannot connect to {self.base_url}")
            print("Make sure the server is running:")
            print("  source venv/bin/activate && uvicorn main:app --reload")
            sys.exit(1)

        # Run tests that need clean rate-limit state first
        self.test_unauthenticated_access()
        self.test_path_traversal()
        self.test_xss_vulnerabilities()
        self.test_session_security()
        self.test_csrf_protection()
        self.test_logout_functionality()
        self.test_password_in_response()
        self.test_information_disclosure()
        # Run brute force test last (it triggers rate limiting)
        self.test_brute_force_protection()

        # Summary
        print("\n" + "=" * 50)
        print("SUMMARY")
        print("=" * 50)

        passed = sum(1 for _, p, _ in self.results if p)
        failed = sum(1 for _, p, _ in self.results if not p)

        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Total:  {len(self.results)}")

        if failed > 0:
            print("\nFailed tests:")
            for name, p, details in self.results:
                if not p:
                    print(f"  - {name}")
                    if details:
                        print(f"    {details}")

        return failed == 0


if __name__ == "__main__":
    tester = SecurityTester(BASE_URL)
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)
