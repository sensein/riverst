# End-to-end tests

Drives the real React client against a real backend in headless Chromium, for
things unit tests cannot reach.

## Setup

```bash
cd tests/e2e
npm install
npx playwright install chromium   # ~95 MB, one time
```

`src/server/.env` must exist so the backend can start, and must have:

- `ENABLE_GOOGLE_AUTH="false"` — otherwise the homepage renders a Google
  sign-in the headless browser cannot get past.
- `OPENAI_API_KEY` set — with no credential the server withholds every hosted
  backend and there is no dropdown left to assert on.

Both are checked before the browser launches, so a missing one is reported by
name rather than as a locator timeout.

## Suites

```bash
node capabilities.test.mjs   # the settings dropdown
```

Scoped to what unit tests cannot reach: the filtering itself is covered by
`src/server/tests/test_capabilities.py`, which runs in milliseconds with no
browser. Only the rendered dropdown needs a real client.

Run manually — there is no CI running tests in this repo, so this is developer
tooling rather than a gate.

## What `capabilities.test.mjs` covers

| Check | Why |
| --- | --- |
| Dropdown matches the server's options, per modality | The component used to hardcode this list, which is what made the `cpu_aws` branch ineffective |
| Options survive repeated modality switches | A later fix mutated the shared schema, so the list compounded away to an empty dropdown |
| UI invents no options of its own | Catches any reintroduced client-side list |

**The backend starts with `RIVERST_LOCAL_MODELS=false` on purpose.** In the
default state the server's offered list is identical to the list the component
used to hardcode, so the dropdown assertions cannot tell the two apart —
verified by reintroducing that bug and watching them pass. With local backends
withheld the server drops ollama, so a hardcoded list stands out immediately.

That variable rather than `RIVERST_COMPUTE_DEVICE` because `main.py` calls
`load_dotenv(override=True)`: `env.example` *ships* `RIVERST_COMPUTE_DEVICE`, so
a `.env` copied from it would beat what the harness passes, while
`RIVERST_LOCAL_MODELS` is shipped commented out. The suite still compares the
served enum against the activity config on disk, so if the filter withheld
nothing it fails instead of passing vacuously.

Both regressions above were reproduced against this suite to confirm it fails on
them, rather than assuming it would.

## Notes

- An empty option list is reported as `[]`, not as a `locator.waitFor` timeout.
  The raw timeout reads like test flakiness and was previously misdiagnosed as
  such when the real cause was the dropdown having been emptied.
- `fetchRetry` exists because a long blocking step can outlive the server's
  keep-alive idle timeout, so a pooled socket fails with `ECONNRESET` before
  reaching the server — which looks exactly like the server having died.
- Activity groups on the homepage are collapsed antd panels, so the group must
  be expanded before the activity card is clickable.
