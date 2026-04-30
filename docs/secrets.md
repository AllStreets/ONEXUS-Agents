# Secrets and environment

The pipeline runs unauthenticated by default but is much faster — and discovers
more — when given API tokens.

## Pipeline (CI / local)

| Variable             | Where used                       | Required? | Notes |
|----------------------|----------------------------------|-----------|-------|
| `GITHUB_TOKEN`       | `pipeline.crawlers.github`       | no        | GitHub provides this automatically in Actions; locally use a fine-grained PAT with `public_repo: read`. |
| `HF_TOKEN`           | `pipeline.crawlers.huggingface`  | no        | Optional — increases rate limits on the public model API. |
| `OPENAI_API_KEY`     | `pipeline.classifier`            | no        | Enables the LLM fallback (default model `gpt-5.4-mini`, override with `ONEXUS_CLASSIFIER_MODEL`) when keyword classification can't decide a category. |

## Site (Vercel)

The site is fully static — no runtime secrets are needed at deploy time.

## Where to set them

- **GitHub Actions:** repo `Settings` → `Secrets and variables` → `Actions` → `New repository secret`.
- **Local development:** `.env` (already gitignored). The pipeline reads from the
  process environment, so `direnv`, `dotenv`, or `export` all work.

## Rotation

There are no service-account credentials in this repo. Tokens are scoped to the
operator running them, so rotation is just "issue a new token, update the secret."

The nightly bot account (`onexus-agents-bot`) commits using the
default `GITHUB_TOKEN` Actions provides — its lifetime is one workflow run.
