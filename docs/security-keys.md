# Secret key management

## Where each key lives

| Key | Dev (laptop) | Prod (droplet) | Vendor console |
|---|---|---|---|
| `OPENAI_API_KEY` | `~/.bas-assistant.env` 600 | `/etc/bas-assistant.env` root 600 | platform.openai.com |
| `ANTHROPIC_API_KEY` | same | same | console.anthropic.com |
| `GEMINI_API_KEY` | same | same | aistudio.google.com |
| `ADMIN_TOKEN` | same | same | generated locally |
| `LANGFUSE_PUBLIC_KEY` | same | same | Langfuse dashboard |
| `LANGFUSE_SECRET_KEY` | same | same | Langfuse dashboard |
| `GRAFANA_ADMIN_PASSWORD` | same | same | generated locally |
| `POSTGRES_PASSWORD` | same | same | generated locally (`openssl rand -hex 16`) |

The droplet file `/etc/bas-assistant.env` is owned by root, mode 600.
Docker Compose reads it via `env_file: ${HOME}/.bas-assistant.env` (dev)
or the same path in prod; no key ever appears in a `docker-compose.yml` literal
or a `Dockerfile` ENV/ARG.

## Vendor spend limits

- **OpenAI**: hard limit $10/month — set at platform.openai.com → Billing → Limits.
- **Anthropic**: set a monthly spend limit at console.anthropic.com → Settings → Limits.
- **Gemini**: free tier (Google AI Studio); no billing enabled unless upgraded.

## GitHub secret scanning + push protection

Turn on at repo Settings → Security → Secret scanning once the repo goes public
(Sunday Sep 27). Enable push protection at the same time. This blocks any future
accidental push of a recognised key shape.

If the `tests/unit/fixtures/fake_keys.txt` fixture raises a GitHub alert, close it
as "used in tests" — it contains clearly fake values.

## 5-minute key rotation procedure

1. Open the vendor console for the affected key and generate a new one.
2. Update `~/.bas-assistant.env` on the laptop (nano, not echo).
3. SSH to the droplet; `sudo nano /etc/bas-assistant.env`; paste the new value.
4. `docker compose restart app` on the droplet.
5. Verify with `make preflight` on the droplet.
6. Revoke the old key in the vendor console.

Total time: ~5 minutes if the vendor console is open.

## If a key is committed

**Rotate first — that is the real fix.**

1. Immediately revoke the key at the vendor console and issue a new one.
2. Update `~/.bas-assistant.env` and the droplet env file.
3. Remove the key from git history:
   ```
   git filter-repo --replace-text <(echo 'LEAKED_VALUE==>REDACTED')
   ```
4. Force-push once: `git push origin main --force` (Jason by hand only — never
   let CI or Claude do this).
5. Notify any team members to re-clone.

The key is already compromised the moment it appears in a commit; rotation is
the real control, not history scrubbing.

## What the guards catch (and what they don't)

The Claude Code hooks, pre-commit gitleaks, and the `test_no_secrets` test are
speed bumps. They catch typos and copy-paste errors. They do **not** protect
against a deliberate attempt to extract a key or against side-channels
(shell history, process lists). The real controls are: keys never enter
Claude's shell environment, they are read at runtime from the file, and the
file is never readable by Claude (denied in `.claude/settings.json`).
