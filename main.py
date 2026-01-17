import os
import re
import secrets
import time
from pathlib import Path
from datetime import datetime
from collections import defaultdict

from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
import markdown

# Configuration
BLOG_PASSWORD = os.environ.get("BLOG_PASSWORD", "secret")
SECRET_KEY = os.environ.get("SECRET_KEY", "your-secret-key-change-in-production")
POSTS_DIR = Path(__file__).parent / "posts"

# Rate limiting configuration
RATE_LIMIT_ATTEMPTS = 5  # Max attempts
RATE_LIMIT_WINDOW = 300  # 5 minutes in seconds

# Disable API docs in production
app = FastAPI(
    title="Private Blog",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# Add session middleware
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# Mount static files
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

# Setup templates
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

# Rate limiting storage (IP -> list of attempt timestamps)
login_attempts: dict[str, list[float]] = defaultdict(list)


def get_client_ip(request: Request) -> str:
    """Get client IP address."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def is_rate_limited(ip: str) -> bool:
    """Check if IP is rate limited."""
    now = time.time()
    # Clean old attempts
    login_attempts[ip] = [t for t in login_attempts[ip] if now - t < RATE_LIMIT_WINDOW]
    return len(login_attempts[ip]) >= RATE_LIMIT_ATTEMPTS


def record_login_attempt(ip: str):
    """Record a failed login attempt."""
    login_attempts[ip].append(time.time())


def generate_csrf_token() -> str:
    """Generate a CSRF token."""
    return secrets.token_urlsafe(32)


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML-like frontmatter from markdown content."""
    frontmatter = {}
    body = content

    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            fm_text = parts[1].strip()
            body = parts[2].strip()

            for line in fm_text.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    frontmatter[key.strip()] = value.strip()

    return frontmatter, body


def get_posts() -> list[dict]:
    """Get all blog posts sorted by date (newest first)."""
    posts = []

    if not POSTS_DIR.exists():
        return posts

    for filepath in POSTS_DIR.glob("*.md"):
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        frontmatter, body = parse_frontmatter(content)

        # Extract title from frontmatter or filename
        title = frontmatter.get("title", filepath.stem.replace("-", " ").title())

        # Extract date from frontmatter or file modification time
        date_str = frontmatter.get("date", "")
        if date_str:
            try:
                date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                date = datetime.fromtimestamp(filepath.stat().st_mtime)
        else:
            date = datetime.fromtimestamp(filepath.stat().st_mtime)

        # Get preview (first paragraph)
        preview = body.split("\n\n")[0][:200] + "..." if len(body) > 200 else body.split("\n\n")[0]

        posts.append({
            "slug": filepath.stem,
            "title": title,
            "date": date,
            "date_str": date.strftime("%B %d, %Y"),
            "preview": preview,
        })

    # Sort by date, newest first
    posts.sort(key=lambda x: x["date"], reverse=True)
    return posts


def get_post(slug: str) -> dict | None:
    """Get a single post by slug."""
    filepath = POSTS_DIR / f"{slug}.md"

    if not filepath.exists():
        return None

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    frontmatter, body = parse_frontmatter(content)

    title = frontmatter.get("title", slug.replace("-", " ").title())
    date_str = frontmatter.get("date", "")

    if date_str:
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            date = datetime.fromtimestamp(filepath.stat().st_mtime)
    else:
        date = datetime.fromtimestamp(filepath.stat().st_mtime)

    # Convert markdown to HTML
    html_content = markdown.markdown(body, extensions=["fenced_code", "tables", "toc"])

    return {
        "slug": slug,
        "title": title,
        "date": date,
        "date_str": date.strftime("%B %d, %Y"),
        "content": html_content,
    }


def is_authenticated(request: Request) -> bool:
    """Check if user is authenticated."""
    return request.session.get("authenticated", False)


def require_auth(request: Request):
    """Dependency to require authentication."""
    if not is_authenticated(request):
        raise HTTPException(status_code=303, headers={"Location": "/login"})


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page - redirect to login or show posts."""
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)

    posts = get_posts()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "posts": posts,
    })


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page."""
    if is_authenticated(request):
        return RedirectResponse(url="/", status_code=303)

    # Generate and store CSRF token in session
    csrf_token = generate_csrf_token()
    request.session["csrf_token"] = csrf_token

    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": None,
        "csrf_token": csrf_token,
    })


@app.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    password: str = Form(...),
    csrf_token: str = Form(...),
):
    """Handle login form submission."""
    client_ip = get_client_ip(request)

    # Check rate limiting
    if is_rate_limited(client_ip):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Too many login attempts. Please try again later.",
            "csrf_token": generate_csrf_token(),
        }, status_code=429)

    # Verify CSRF token
    session_csrf = request.session.get("csrf_token", "")
    if not secrets.compare_digest(csrf_token, session_csrf):
        new_csrf = generate_csrf_token()
        request.session["csrf_token"] = new_csrf
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid request. Please try again.",
            "csrf_token": new_csrf,
        }, status_code=403)

    # Verify password
    if secrets.compare_digest(password, BLOG_PASSWORD):
        request.session["authenticated"] = True
        request.session.pop("csrf_token", None)  # Clear CSRF token after successful login
        return RedirectResponse(url="/", status_code=303)

    # Record failed attempt
    record_login_attempt(client_ip)

    # Generate new CSRF token for retry
    new_csrf = generate_csrf_token()
    request.session["csrf_token"] = new_csrf

    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": "Invalid password",
        "csrf_token": new_csrf,
    })


@app.get("/logout")
async def logout(request: Request):
    """Logout and clear session."""
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


@app.get("/post/{slug}", response_class=HTMLResponse)
async def view_post(request: Request, slug: str):
    """View a single post."""
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)

    post = get_post(slug)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    return templates.TemplateResponse("post.html", {
        "request": request,
        "post": post,
    })


def slugify(title: str) -> str:
    """Convert title to URL-safe slug."""
    slug = title.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug[:50]  # Limit length


@app.get("/new", response_class=HTMLResponse)
async def new_post_page(request: Request):
    """New post page."""
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)

    csrf_token = generate_csrf_token()
    request.session["csrf_token"] = csrf_token

    return templates.TemplateResponse("new_post.html", {
        "request": request,
        "csrf_token": csrf_token,
        "error": None,
        "success": None,
        "title": "",
        "content": "",
    })


@app.post("/new", response_class=HTMLResponse)
async def create_post(
    request: Request,
    title: str = Form(...),
    content: str = Form(...),
    csrf_token: str = Form(...),
):
    """Create a new post."""
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)

    # Verify CSRF token
    session_csrf = request.session.get("csrf_token", "")
    if not secrets.compare_digest(csrf_token, session_csrf):
        new_csrf = generate_csrf_token()
        request.session["csrf_token"] = new_csrf
        return templates.TemplateResponse("new_post.html", {
            "request": request,
            "csrf_token": new_csrf,
            "error": "Invalid request. Please try again.",
            "success": None,
            "title": title,
            "content": content,
        }, status_code=403)

    # Generate slug from title
    slug = slugify(title)
    if not slug:
        new_csrf = generate_csrf_token()
        request.session["csrf_token"] = new_csrf
        return templates.TemplateResponse("new_post.html", {
            "request": request,
            "csrf_token": new_csrf,
            "error": "Please enter a valid title.",
            "success": None,
            "title": title,
            "content": content,
        })

    # Check if post already exists
    filepath = POSTS_DIR / f"{slug}.md"
    if filepath.exists():
        # Add timestamp to make unique
        slug = f"{slug}-{int(time.time())}"
        filepath = POSTS_DIR / f"{slug}.md"

    # Create post with frontmatter
    today = datetime.now().strftime("%Y-%m-%d")
    post_content = f"""---
title: {title}
date: {today}
---

{content}
"""

    # Save the post
    POSTS_DIR.mkdir(exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(post_content)

    # Redirect to the new post
    return RedirectResponse(url=f"/post/{slug}", status_code=303)


@app.post("/api/preview", response_class=HTMLResponse)
async def preview_markdown(request: Request):
    """API endpoint to preview markdown content."""
    if not is_authenticated(request):
        raise HTTPException(status_code=401)

    body = await request.json()
    content = body.get("content", "")
    html = markdown.markdown(content, extensions=["fenced_code", "tables", "toc"])
    return HTMLResponse(content=html)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
