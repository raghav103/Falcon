# Contributing to Falcon

Thank you for your interest in contributing to Falcon! This document provides guidelines and instructions for development.

## Development Setup

1. **Fork and clone the repository:**
   ```bash
   git clone https://github.com/your-username/falcon.git
   cd falcon
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies (including dev dependencies):**
   ```bash
   pip install -r requirements-dev.txt
   ```

4. **Set up environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your local configuration
   ```

5. **Create database:**
   ```bash
   createdb falcon
   ```

6. **Run the server:**
   ```bash
   uvicorn backend.main:app --reload
   ```

## Code Standards

### Formatting

We use [Black](https://github.com/psf/black) for code formatting:

```bash
black backend/
```

**Line length**: 100 characters

###Linting

We use [Ruff](https://github.com/astral-sh/ruff) for linting:

```bash
ruff check backend/
```

Fix automatically where possible:

```bash
ruff check --fix backend/
```

### Type Checking

We use [mypy](https://mypy.readthedocs.io/) for static type checking:

```bash
mypy backend/
```

### Testing

Run tests with pytest:

```bash
pytest

# With coverage
pytest --cov=backend --cov-report=html
```

All tests must pass before submitting a pull request.

### Pre-commit Checklist

Before committing, ensure:

- [ ] Code is formatted with `black backend/`
- [ ] No linting errors from `ruff check backend/`
- [ ] Type checking passes with `mypy backend/`
- [ ] All tests pass with `pytest`
- [ ] New features have tests
- [ ] Documentation is updated (README, docstrings, etc.)

## Commit Messages

Use clear, descriptive commit messages following conventional commits:

- `feat: Add rate limiting to API endpoints`
- `fix: Handle git clone timeout errors`
- `docs: Update README with authentication instructions`
- `test: Add integration tests for chat endpoint`
- `refactor: Extract validation logic to separate module`
- `chore: Update dependencies`

## Pull Request Process

1. **Create a feature branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following the code standards above

3. **Write tests** for new functionality

4. **Update documentation:**
   - Update README.md if adding new features or changing behavior
   - Add/update docstrings for new functions and modules
   - Update API documentation if endpoints change

5. **Run all checks:**
   ```bash
   black backend/
   ruff check backend/
   mypy backend/
   pytest
   ```

6. **Commit your changes:**
   ```bash
   git add .
   git commit -m "feat: your feature description"
   ```

7. **Push to your fork:**
   ```bash
   git push origin feature/your-feature-name
   ```

8. **Create a Pull Request:**
   - Go to the original repository on GitHub
   - Click "New Pull Request"
   - Select your fork and branch
   - Fill in the PR template with:
     - Description of changes
     - Related issues (if any)
     - Testing performed
     - Screenshots (if UI changes)

9. **Respond to review feedback:**
   - Address comments from reviewers
   - Make requested changes
   - Push updates to your branch

## What to Contribute

### Good First Issues

Look for issues labeled `good first issue` for beginner-friendly tasks.

### Ideas for Contributions

- **Bug fixes**: Fix reported bugs or edge cases
- **Tests**: Increase test coverage
- **Documentation**: Improve README, add examples, write tutorials
- **Performance**: Optimize database queries, reduce memory usage
- **Features**: Implement items from the roadmap (check `architecture.md`)

### Not Accepting

- Large architectural changes without prior discussion
- Breaking changes to existing APIs without migration path
- Dependencies that significantly increase bundle size
- Features that duplicate existing functionality

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on the code, not the person
- Help others learn and grow

## Getting Help

- **Questions**: Open a GitHub Discussion
- **Bugs**: Open a GitHub Issue with reproduction steps
- **Security**: See [SECURITY.md](SECURITY.md)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to Falcon! 🚀
