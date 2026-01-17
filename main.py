import os
import re
from pathlib import Path
from datetime import datetime

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

app = FastAPI(title="Private Blog")

# Add session middleware
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# Mount static files
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

# Setup templates
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


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

    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": None,
    })


@app.post("/login", response_class=HTMLResponse)
async def login(request: Request, password: str = Form(...)):
    """Handle login form submission."""
    if password == BLOG_PASSWORD:
        request.session["authenticated"] = True
        return RedirectResponse(url="/", status_code=303)

    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": "Invalid password",
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
