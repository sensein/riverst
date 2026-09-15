/**
 * End-to-end checks for deployment capability filtering.
 *
 * The point of these is the settings dropdown. The server filters which model
 * services it offers, but the frontend used to overwrite that list with a
 * hardcoded one -- which is what made the `cpu_aws` branch ineffective. A fix
 * for that then introduced a second bug by mutating the shared schema, so the
 * list degraded as the user switched pipeline modality.
 *
 * Both bugs are invisible to server-side tests and to "does the form render",
 * so they are asserted here against a real browser.
 *
 * Run with: node tests/e2e/capabilities.test.mjs   (see README.md)
 */

import { chromium } from 'playwright'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import {
  API_PORT,
  REPO,
  CHROMIUM_ARGS,
  WEB_PORT,
  dumpLogs,
  fetchRetry,
  startBackend,
  startFrontend,
  stopAll,
} from './harness.mjs'

const ACTIVITY = 'basic-avatar-interaction'
const ACTIVITY_CARD = 'Free style interaction'
const ACTIVITY_GROUP = 'Playground just for fun'

// antd leaves closed dropdown portals in the DOM, so every option query must be
// scoped to the dropdown that is currently open. Without this the first match
// is a stale hidden portal and the wait times out.
const OPEN_DROPDOWN = '.ant-select-dropdown:not(.ant-select-dropdown-hidden)'

const results = []
let browser

function pass(name, note = '') {
  results.push({ name, ok: true })
  console.log(`  PASS  ${name}${note ? ` — ${note}` : ''}`)
}
function fail(name, why) {
  results.push({ name, ok: false, note: why })
  console.log(`  FAIL  ${name} — ${why}`)
}

/** Open the activity settings form, expanding the collapsed group first. */
async function openSettingsForm(page) {
  await page.goto(`http://127.0.0.1:${WEB_PORT}/`)
  await page.getByText(ACTIVITY_GROUP).first().click({ timeout: 30000 })
  await page.getByText(ACTIVITY_CARD).first().click({ timeout: 30000 })
  await page
    .locator('.ant-form-item', { hasText: /PIPELINE MODALITY/i })
    .waitFor({ timeout: 30000 })
}

async function selectModality(page, value) {
  const select = page
    .locator('.ant-form-item', { hasText: /PIPELINE MODALITY/i })
    .locator('.ant-select')
  await select.click()
  await page.locator(`${OPEN_DROPDOWN} .ant-select-item-option[title="${value}"]`).click()
  await page.waitForTimeout(700)
}

async function readLlmOptions(page) {
  const select = page
    .locator('.ant-form-item', { hasText: /LLM TYPE/i })
    .locator('.ant-select')
  await select.click()
  const options = page.locator(`${OPEN_DROPDOWN} .ant-select-item-option`)
  let values = []
  try {
    await options.first().waitFor({ timeout: 10000 })
    values = (await options.allInnerTexts()).map((o) => o.trim())
  } catch (e) {
    // An option list with nothing in it renders antd's empty state, so the
    // wait above times out. Returning [] rather than propagating a
    // `locator.waitFor timeout` matters: that raw message reads like test
    // flakiness, and it was previously misdiagnosed as such when the real
    // cause was the dropdown having been emptied.
    //
    // Confirmed against the empty state rather than assumed, though: a
    // crashed or navigated-away page times out here too, and reporting that
    // as an emptied dropdown would blame the schema for a dead browser.
    const empty = await page.locator(`${OPEN_DROPDOWN} .ant-empty`).count()
    if (!empty) throw e
    values = []
  }
  await page.keyboard.press('Escape')
  await page.waitForTimeout(300)
  return values
}

async function main() {
  // The backend runs in cpu mode deliberately. In auto mode the server's
  // offered list is identical to the list the component used to hardcode, so
  // the dropdown assertions cannot tell the two apart -- verified by
  // reintroducing that bug and watching them pass. In cpu mode the server
  // drops ollama, so a hardcoded list stands out immediately.
  // RIVERST_LOCAL_MODELS rather than RIVERST_COMPUTE_DEVICE: main.py calls
  // load_dotenv(override=True), and env.example *ships*
  // RIVERST_COMPUTE_DEVICE, so a .env copied from it would beat anything
  // passed here. RIVERST_LOCAL_MODELS is shipped commented out, so it survives
  // and withholds local backends deterministically -- the state these
  // assertions need, since in the default state the server's list is identical
  // to the list the component used to hardcode.
  console.log('Starting backend (local models withheld) and frontend…')
  await startBackend({ env: { RIVERST_LOCAL_MODELS: 'false' } })
  await startFrontend()

  // What the server offers, as the UI will receive it.
  const cfg = await (
    await fetchRetry(
      `http://127.0.0.1:${API_PORT}/api/activities/${ACTIVITY}/session_config`
    )
  ).json()
  const llmProp = cfg?.properties?.options?.properties?.llm_type
  if (!llmProp?.enum?.length) {
    fail(
      'server offers an llm_type',
      'the server deleted llm_type entirely, which happens when no credential ' +
        'is available. Set OPENAI_API_KEY in src/server/.env and re-run.'
    )
    return false
  }
  const serverEnum = llmProp.enum
  const expectRealtime = serverEnum.filter((v) => v.startsWith('openai_gpt-realtime'))
  const expectClassic = serverEnum.filter((v) => !v.startsWith('openai_gpt-realtime'))
  console.log(`  server offers: ${serverEnum.join(', ')}`)

  // Every assertion below compares the dropdown against this same response, so
  // if the server-side filter never engaged the suite would pass vacuously:
  // ollama would be offered, expected and shown. main.py loads .env with
  // override=True, so RIVERST_COMPUTE_DEVICE from startBackend loses to a .env
  // that sets it -- assert the mode rather than assume it.
  // Compared against the config on disk, not just checked for absence: if a
  // future edit removed ollama from the config, an absence check would still
  // pass while the suite silently lost the ability to tell a correct dropdown
  // from a hardcoded one.
  const onDisk = JSON.parse(
    readFileSync(
      join(REPO, 'src/server/activities', ACTIVITY, 'session_config.json'),
      'utf-8'
    )
  ).properties.options.properties.llm_type.enum
  const withheld = onDisk.filter((v) => !serverEnum.includes(v))
  if (!withheld.length) {
    fail(
      'server withheld at least one local backend',
      `served list matches the config on disk (${onDisk.join(', ')}), so the ` +
        'filter did not remove anything. These assertions cannot distinguish a ' +
        'correct dropdown from a hardcoded one in that state.'
    )
    return false
  }
  pass('server withheld at least one local backend', withheld.join(', '))

  // Checked rather than assumed: with Google auth on, the homepage renders a
  // sign-in screen the headless browser cannot get past, and every locator
  // below fails as an opaque 30s timeout instead of naming the cause.
  const auth = await (
    await fetchRetry(`http://127.0.0.1:${API_PORT}/api/auth/status`)
  ).json()
  if (auth.google_auth_enabled) {
    fail(
      'auth is bypassable',
      'ENABLE_GOOGLE_AUTH is true, so the homepage requires a real Google ' +
        'sign-in. Set ENABLE_GOOGLE_AUTH="false" in src/server/.env to run this ' +
        'suite.'
    )
    return false
  }
  pass('auth is bypassable')

  browser = await chromium.launch({ args: CHROMIUM_ARGS })
  const page = await browser.newPage()

  try {
    await openSettingsForm(page)
    pass('settings form opens')
  } catch (e) {
    fail('settings form opens', e.message)
    return false
  }

  // JSON.stringify, not join(): model names contain commas nowhere today, but
  // a joined comparison silently equates ['a,b'] with ['a','b'].
  const sameSet = (a, b) =>
    a.length === b.length &&
    JSON.stringify([...a].sort()) === JSON.stringify([...b].sort())

  // 1. Each modality shows exactly what the server offers for it. The old
  //    hardcoded list would fail this as soon as the server's list changed.
  try {
    await selectModality(page, 'e2e')
    const e2eOpts = await readLlmOptions(page)
    if (sameSet(e2eOpts, expectRealtime)) {
      pass('e2e dropdown matches the server-offered realtime options', e2eOpts.join(', '))
    } else {
      fail(
        'e2e dropdown matches the server-offered realtime options',
        `expected [${expectRealtime}] got [${e2eOpts}]`
      )
    }

    await selectModality(page, 'classic')
    const classicOpts = await readLlmOptions(page)
    if (sameSet(classicOpts, expectClassic)) {
      pass('classic dropdown matches the server-offered classic options', classicOpts.join(', '))
    } else {
      fail(
        'classic dropdown matches the server-offered classic options',
        `expected [${expectClassic}] got [${classicOpts}]`
      )
    }

    // 2. Regression guard for the schema-mutation bug: the filter must be
    //    idempotent across modality switches. When the component wrote its
    //    filtered list back into the shared schema, the options compounded away
    //    to nothing -- e2e then classic yielded an empty dropdown.
    await selectModality(page, 'e2e')
    const e2eAgain = await readLlmOptions(page)
    await selectModality(page, 'classic')
    const classicAgain = await readLlmOptions(page)

    if (e2eAgain.length && sameSet(e2eAgain, expectRealtime)) {
      pass('options survive repeated modality switches (e2e)', e2eAgain.join(', '))
    } else {
      fail(
        'options survive repeated modality switches (e2e)',
        `dropdown degraded to [${e2eAgain}] — the schema is being mutated`
      )
    }
    if (classicAgain.length && sameSet(classicAgain, expectClassic)) {
      pass('options survive repeated modality switches (classic)', classicAgain.join(', '))
    } else {
      fail(
        'options survive repeated modality switches (classic)',
        `dropdown degraded to [${classicAgain}] — the schema is being mutated`
      )
    }

    // 3. Nothing the server did not offer may appear, in either modality.
    const invented = [...e2eAgain, ...classicAgain].filter((o) => !serverEnum.includes(o))
    if (!invented.length) {
      pass('UI invents no options of its own')
    } else {
      fail('UI invents no options of its own', `not from server: [${invented}]`)
    }
  } catch (e) {
    fail('dropdown assertions', e.message)
  }

  await page.close()
  await browser.close()
  browser = null

  return results.every((r) => r.ok)
}

/**
 * Printed from `finally`, not from the end of main: several checks bail out
 * early, and the run that bails is the run whose backend log you need.
 */
function summarize() {
  const failed = results.filter((r) => !r.ok)
  console.log(`\n${'='.repeat(60)}`)
  console.log(`${results.length - failed.length}/${results.length} checks passed`)
  if (!failed.length) return
  console.log('\nFailures:')
  for (const f of failed) console.log(`  - ${f.name}: ${f.note}`)
  console.log('\nBackend output tail:')
  console.log(dumpLogs('backend').split('\n').slice(-30).join('\n'))
}

let ok = false
try {
  ok = await main()
} catch (e) {
  console.error('\nHarness error:', e)
  results.push({ name: 'harness completes', ok: false, note: String(e?.message ?? e) })
} finally {
  if (browser) await browser.close().catch(() => {})
  summarize()
  stopAll()
}
// exitCode rather than process.exit(): the latter can truncate stdout when it
// is a pipe, which is exactly how this suite gets run from CI or a tee.
process.exitCode = ok && results.length && results.every((r) => r.ok) ? 0 : 1
