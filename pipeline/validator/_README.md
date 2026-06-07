# Validator

The validator is the gate for every PR that touches `catalog/`.

## Run locally

```sh
# one file
onexus-agents-validate catalog/coding/aider.json

# a whole directory
onexus-agents-validate catalog/coding

# the entire catalog
onexus-agents-validate
```

## What it checks

1. JSON parses.
2. Pydantic schema matches `pipeline.schema.Agent`.
3. The file is under `catalog/<category>/` matching its `category` field.
4. The filename matches the `slug` field.
5. The `category` is one of the slugs in `catalog/_categories.json`.
6. `source.primary=github` ⇒ `source.github` is non-null (and the same for huggingface).
7. `runnable: true` ⇒ `adapter_ref` is non-null.

## CI

The `validate` workflow runs the validator against the entire catalog on every
push to `main` and every PR that touches `catalog/`, `pipeline/`, `validator/`,
or `pyproject.toml`.
