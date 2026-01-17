---
title: Welcome to Your Private Blog
date: 2025-01-17
---

Welcome to your new private blog! This is a simple, password-protected blog built with FastAPI.

## Features

- **Password Protection**: All blog content is protected behind a login page
- **Markdown Support**: Write posts in Markdown format with full formatting support
- **Clean Design**: Simple, readable styling that works on all devices
- **Easy to Use**: Just add `.md` files to the `posts/` directory

## Writing Posts

To create a new post, add a Markdown file to the `posts/` directory. Each post can include frontmatter at the top:

```markdown
---
title: My Post Title
date: 2025-01-17
---

Your content here...
```

## Markdown Examples

Here are some examples of what you can do:

### Text Formatting

You can use **bold**, *italic*, and `inline code`.

### Lists

- Item one
- Item two
- Item three

### Code Blocks

```python
def hello():
    print("Hello, World!")
```

### Blockquotes

> This is a blockquote. It's useful for highlighting important information.

## Getting Started

1. Set your blog password via the `BLOG_PASSWORD` environment variable
2. Add your posts to the `posts/` directory
3. Run the server with `uvicorn main:app --reload`

Happy blogging!
