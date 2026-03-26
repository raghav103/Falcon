# Security Policy

## Supported Versions

Currently supporting:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

**Please do NOT open public GitHub issues for security vulnerabilities.**

To report a security vulnerability, please email:

**[your-email@domain.com]** (replace with actual contact)

Include in your report:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

You should receive a response within 48 hours. If the vulnerability is confirmed, we will:

1. Work on a fix
2. Release a security update
3. Credit you in the security advisory (unless you prefer to remain anonymous)

## Security Measures

Falcon implements several security best practices:

### Authentication
- **API Key Authentication**: All endpoints (except `/health`) require `X-API-Key` header
- Configurable per environment
- Optional in development mode for easier testing

### Input Validation
- **Git URL Validation**: Prevents command injection attacks
  - Only HTTPS and SSH URLs allowed
  - Blocks suspicious characters (`;`, `|`, `&`, `$`, `` ` ``)
  - Blocks local file paths and private networks
- **Message History Validation**: Prevents malicious chat history injection
  - Max 50 messages
  - Max 10,000 characters per message
  - Role validation (user/assistant only)

### Error Handling
- **Safe Error Messages**: Internal errors logged server-side, generic messages returned to clients
- No stack traces or internal details exposed in API responses
- Structured logging for audit trails

### CORS Configuration
- Configurable origins (not wildcard `*`)
- Explicit methods: GET, POST, DELETE (not `*`)
- Explicit headers: Content-Type, X-API-Key (not `*`)

### Database Security
- **Parameterized Queries**: All SQL uses parameterized statements (no SQL injection risk)
- Connection pooling with limits
- Automatic schema validation

### Dependency Security
- Minimal dependencies
- Regular updates
- No known vulnerabilities in current dependencies

## Known Limitations

### Current Version (0.1.x)

1. **No Rate Limiting**: API can be abused without rate limits
   - **Mitigation**: Implement rate limiting middleware (planned)
   - **Workaround**: Use nginx or API gateway with rate limiting

2. **Synchronous Ingestion**: Large repository ingestion can timeout
   - **Mitigation**: Move to background job queue (see `architecture.md`)
   - **Workaround**: Ingest smaller repositories or increase timeout

3. **No Request Size Limits**: Large requests not explicitly limited
   - **Mitigation**: Add request size middleware
   - **Workaround**: Configure at reverse proxy level (nginx, etc.)

4. **Simple API Key Auth**: Single shared API key, no per-user authentication
   - **Mitigation**: Implement OAuth2/JWT (planned)
   - **Workaround**: Use API gateway for advanced auth

### Private Repository Support

Currently, Falcon only supports public repositories accessible via HTTPS/SSH without authentication.

**Do NOT:**
- Clone private repositories without proper authentication
- Expose sensitive repositories
- Use credentials in URLs

## Security Checklist for Deployment

Before deploying to production:

- [ ] Set strong `API_KEY` in environment variables
- [ ] Configure `CORS_ORIGINS` to specific allowed origins
- [ ] Set `ENVIRONMENT=production`
- [ ] Use HTTPS (TLS/SSL) for all connections
- [ ] Configure PostgreSQL with authentication and encryption
- [ ] Set up firewall rules (only allow necessary ports)
- [ ] Enable structured logging for audit trails
- [ ] Monitor logs for suspicious activity
- [ ] Keep dependencies updated
- [ ] Use secrets management (not `.env` files in production)
- [ ] Consider adding rate limiting at application or gateway level
- [ ] Regular backups of database

## Responsible Disclosure

We follow responsible disclosure practices:

1. Report received → Acknowledged within 48 hours
2. Fix developed → with your input if desired
3. Security update released
4. Public disclosure → after fix deployed and users notified

We appreciate security researchers who:
- Allow reasonable time for fixes
- Do not exploit vulnerabilities
- Do not access/modify user data
- Report issues privately first

## Contact

For security concerns: **[your-email@domain.com]**

For general issues: Open a GitHub issue

---

Thank you for helping keep Falcon secure!
