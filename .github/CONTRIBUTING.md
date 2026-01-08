# Contributing to MS Brief Agent

Thank you for your interest in contributing! MS Brief Agent is an open-source project and welcomes contributions from the community.

## 📋 Code of Conduct

Be respectful, inclusive, and professional. We're building this together.

---

## 🚀 Ways to Contribute

### Report Bugs

**Found an issue?** Help us fix it!

1. **Search existing issues** first: [GitHub Issues](https://github.com/YOUR_USERNAME/ms-brief-agent/issues)
2. **Create a new issue** if not already reported
3. **Include details**:
   - Clear, descriptive title
   - Steps to reproduce
   - Expected vs. actual behavior
   - Environment: Python version, OS, deployment method
   - Error messages and logs (sanitized - no secrets!)

### Suggest Features

**Have an idea?** Share it!

1. **Check discussions**: [GitHub Discussions](https://github.com/YOUR_USERNAME/ms-brief-agent/discussions)
2. **Start a discussion** with:
   - Clear title
   - Detailed description
   - Use cases and benefits
   - Implementation approach (optional)

### Submit Code

**Want to code?** Great! Here's the workflow.

## 🔧 Development Workflow

### 1. Fork and Clone

```bash
git clone https://github.com/YOUR_USERNAME/ms-brief-agent.git
cd ms-brief-agent
```

### 2. Create Feature Branch

```bash
git checkout -b feature/your-feature-name
```

Good branch names:
- `feature/slack-integration`
- `fix/teams-webhook-timeout`
- `docs/deployment-guide`

### 3. Development Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install --pre -r requirements.txt

# Verify setup
python -m pytest tests/ -v
```

### 4. Make Changes

- Keep commits focused and logical
- Write clear commit messages
- Add tests for new code
- Update documentation
- Follow code style guidelines

### 5. Test Your Changes

```bash
# Run all tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov-report=html
```

### 6. Code Quality

```bash
# Format with black
black src/ --line-length=100

# Check style
flake8 src/ --max-line-length=100
```

### 7. Commit and Push

```bash
git add .
git commit -m "feat: Add new feature"
git push origin feature/your-feature-name
```

### 8. Create Pull Request

1. Go to GitHub
2. Click "Compare & pull request"
3. Describe your changes
4. Link related issues
5. Wait for review

---

## 📝 Coding Standards

- **Python**: 3.11+
- **Style**: PEP 8
- **Type hints**: Required for new code
- **Docstrings**: Required for functions/classes (Google style)

### Code Style Example

```python
async def fetch_message_center(
    tenant_id: str,
    days_back: int = 7,
) -> list[dict]:
    """
    Fetch Microsoft Message Center announcements.
    
    Args:
        tenant_id: Azure AD tenant ID
        days_back: Number of days to look back
        
    Returns:
        List of announcements
        
    Raises:
        ValueError: If days_back is invalid
    """
    if days_back < 0:
        raise ValueError("days_back must be non-negative")
    # Implementation...
```

---

## 🔨 Commit Message Guidelines

Use Conventional Commits format:

```
feat: Add new feature
fix: Resolve bug
docs: Update documentation
test: Add tests
refactor: Improve code
```

Examples:

```
feat(teams): Add rich message formatting
fix(auth): Resolve token expiration
docs: Update deployment guide
```

---

## ✅ Pull Request Checklist

- [ ] Code follows PEP 8
- [ ] Tests pass (`pytest tests/`)
- [ ] New features have tests
- [ ] Documentation updated
- [ ] No secrets in code
- [ ] Branch is up-to-date

---

## 🚀 Release Process

(For maintainers)

1. Update version
2. Update CHANGELOG
3. Create GitHub Release
4. Tests run automatically
5. Publish to PyPI (future)

---

## 💬 Questions?

- 📖 [Documentation](../docs/)
- 🐛 [GitHub Issues](https://github.com/YOUR_USERNAME/ms-brief-agent/issues)
- 💬 [Discussions](https://github.com/YOUR_USERNAME/ms-brief-agent/discussions)

---

**Thank you for contributing!** 🚀
