# Private Blog

A password-protected personal blog built with FastAPI and Markdown.

## Tech Stack

- **Backend:** Python FastAPI
- **Auth:** Session-based password protection
- **Storage:** Markdown files with frontmatter
- **Templates:** Jinja2
- **Styling:** Claude-inspired design (warm beige, terracotta accents)

## Project Structure

```
test/
├── main.py              # FastAPI application
├── posts/               # Markdown blog posts
│   └── example.md       # Sample post
├── templates/           # HTML templates
│   ├── base.html        # Base layout
│   ├── login.html       # Login page
│   ├── index.html       # Blog home (post list)
│   └── post.html        # Single post view
├── static/              # Static files
│   └── style.css        # CSS styling
└── requirements.txt     # Python dependencies
```

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Run the server
uvicorn main:app --reload

# Or run directly
python main.py
```

Open http://localhost:8000 in your browser.

## Configuration

Set environment variables to customize:

```bash
# Set blog password (default: "secret")
export BLOG_PASSWORD="your-password"

# Set session secret key (change in production)
export SECRET_KEY="your-secret-key"
```

## Writing Posts

Add Markdown files to the `posts/` directory with optional frontmatter:

```markdown
---
title: My Post Title
date: 2025-01-17
---

Your content here...
```

Supported Markdown features:
- Headings, paragraphs, lists
- Code blocks with syntax highlighting
- Tables
- Blockquotes
- Images
- Links

## Design

Claude-inspired styling with:
- Warm beige background (`#f5f0e8`)
- Cream white cards (`#fffcf7`)
- Terracotta accent color (`#da7756`)
- Clean typography with refined letter-spacing
- Mobile responsive layout
