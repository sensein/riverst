/**
 * Process management for the end-to-end tests.
 *
 * Stands up an isolated backend and a Vite dev server pointed at it, then
 * drives the real React client in headless Chromium.
 */

import { execSync, spawn } from 'node:child_process'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
export const REPO = join(HERE, '..', '..')
export const SERVER_DIR = join(REPO, 'src', 'server')
export const CLIENT_DIR = join(REPO, 'src', 'client', 'react')

// Isolated ports so a developer's own running instance is untouched.
export const API_PORT = 7877
export const WEB_PORT = 5188

const procs = []

function waitForHttp(url, { timeoutMs = 90000, label = url, entry = null } = {}) {
  const deadline = Date.now() + timeoutMs
  return (async () => {
    for (;;) {
      try {
        const res = await fetch(url)
        // Only a server WE started counts. Both ports use --strictPort, so a
        // squatter from another checkout (or a leaked run) makes our child exit
        // while the port keeps answering -- and every assertion then runs
        // against someone else's working tree, passing or failing for reasons
        // that have nothing to do with the code under test. This cost hours
        // once; it is not allowed to be silent again.
        if (res.ok) {
          if (entry?.exited) {
            throw new Error(
              `${label} exited but ${url} still answers -- something else is ` +
                `holding that port (a leaked run, or a dev server from another ` +
                `checkout). Kill it and re-run:\n` +
                `  lsof -nP -iTCP -sTCP:LISTEN | grep -E ':(${API_PORT}|${WEB_PORT}) '\n` +
                entry.log.join('')
            )
          }
          return
        }
      } catch (e) {
        if (e instanceof Error && e.message.includes('still answers')) throw e
        // not up yet
      }
      // Fail immediately if the process is already gone, rather than polling a
      // dead port for the full timeout and reporting it as slowness.
      if (entry?.error) {
        throw new Error(`${label} failed to start: ${entry.error.message}`)
      }
      if (entry?.exited) {
        throw new Error(`${label} exited before serving:\n${entry.log.join('')}`)
      }
      if (Date.now() > deadline) throw new Error(`Timed out waiting for ${label}`)
      await new Promise((r) => setTimeout(r, 500))
    }
  })()
}

function start(cmd, args, opts, name) {
  // detached so the child gets its own process group: `npm run dev` runs vite
  // as a grandchild, and killing only npm would leave vite holding the port --
  // which --strictPort then turns into an unexplained timeout on the next run.
  const p = spawn(cmd, args, {
    ...opts,
    stdio: ['ignore', 'pipe', 'pipe'],
    detached: true,
  })
  const log = []
  const entry = { proc: p, name, log, exited: false, error: null }
  p.stdout.on('data', (d) => log.push(d.toString()))
  p.stderr.on('data', (d) => log.push(d.toString()))
  // Without an 'error' listener a missing interpreter (ENOENT) escalates to an
  // uncaught exception instead of a readable failure.
  p.on('error', (e) => {
    entry.error = e
    log.push(`spawn failed: ${e.message}\n`)
  })
  p.on('exit', (code, signal) => {
    entry.exited = true
    // `code` is null when the process was signalled, so checking it alone
    // logs nothing for the kill -9 / OOM case.
    if (code || signal) log.push(`exited with code ${code} (signal ${signal})\n`)
  })
  procs.push(entry)
  return { proc: p, log, entry }
}

/**
 * Start a backend on an isolated port, capturing its output into `procs`.
 *
 * @param {object} [opts]
 * @param {number} [opts.port] Defaults to API_PORT.
 * @param {object} [opts.env] Extra environment, e.g. RIVERST_LOCAL_MODELS.
 *   IMPORTANT: main.py calls load_dotenv(override=True), so any variable also
 *   present in src/server/.env wins over what is passed here. Prefer variables
 *   env.example ships commented out (RIVERST_LOCAL_MODELS) over ones it sets
 *   (RIVERST_COMPUTE_DEVICE), and assert the resulting state rather than
 *   assuming this took effect.
 * @param {string} [opts.name] Process label used in dumped logs.
 */
function listenersOn(port) {
  try {
    return execSync(`lsof -ti tcp:${port} -sTCP:LISTEN`, { stdio: ['ignore', 'pipe', 'ignore'] })
      .toString()
      .split('\n')
      .map((l) => l.trim())
      .filter(Boolean)
  } catch {
    return [] // lsof exits non-zero when nothing matches
  }
}

function describePid(pid) {
  try {
    return execSync(`ps -o command= -p ${pid}`, { stdio: ['ignore', 'pipe', 'ignore'] })
      .toString()
      .trim()
      .slice(0, 120)
  } catch {
    return '<gone>'
  }
}

/**
 * Take back a port this suite owns, killing a leaked server if one holds it.
 *
 * Both ports are claimed with --strictPort, so a squatter makes our own child
 * exit while the port keeps answering -- and then every assertion runs against
 * a different working tree and passes for reasons unrelated to the code under
 * test. That happened: leftover vite servers from an interrupted run served the
 * main checkout while the suite reported success against a worktree, and a real
 * bug shipped behind a green run.
 *
 * Reclaiming rather than only refusing, because an interrupted run is the
 * normal way one leaks and the next run should just work. These two ports are
 * private to this suite (deliberately not vite's default 5173), so nothing here
 * should ever belong to a real dev server -- but it always says what it killed,
 * so it cannot be silent.
 */
async function reclaimPort(port, label) {
  const answering = async () => {
    try {
      await fetch(`http://127.0.0.1:${port}/`, { signal: AbortSignal.timeout(1500) })
      return true
    } catch {
      return false
    }
  }
  const pids = listenersOn(port)
  if (!pids.length && !(await answering())) return

  for (const pid of pids) {
    console.log(`  reclaiming port ${port} from pid ${pid}: ${describePid(pid)}`)
    try {
      process.kill(Number(pid), 'SIGTERM')
    } catch {
      // already gone
    }
  }
  for (let i = 0; i < 20; i++) {
    if (!listenersOn(port).length && !(await answering())) return
    await new Promise((r) => setTimeout(r, 250))
  }
  for (const pid of listenersOn(port)) {
    try {
      process.kill(Number(pid), 'SIGKILL')
    } catch {
      // already gone
    }
  }
  await new Promise((r) => setTimeout(r, 500))
  if (await answering()) {
    throw new Error(
      `Port ${port} is still serving something after SIGTERM and SIGKILL, so ` +
        `the ${label} this suite starts would not be the one under test:\n` +
        `  lsof -nP -iTCP -sTCP:LISTEN | grep ':${port} '`
    )
  }
}

export async function startBackend({ port = API_PORT, env = {}, name = 'backend' } = {}) {
  await reclaimPort(port, 'backend')
  const { log, entry } = start(
    'python',
    ['main.py', '--port', String(port)],
    { cwd: SERVER_DIR, env: { ...process.env, ...env } },
    name
  )
  await waitForHttp(`http://127.0.0.1:${port}/api/health`, { label: name, entry })
  return { log }
}

/** Start the Vite dev server, proxying /api to our isolated backend. */
export async function startFrontend() {
  await reclaimPort(WEB_PORT, 'frontend')
  const { log, entry } = start(
    'npm',
    ['run', 'dev', '--', '--port', String(WEB_PORT), '--strictPort', '--host', '127.0.0.1'],
    {
      cwd: CLIENT_DIR,
      env: { ...process.env, VITE_API_PROXY_TARGET: `http://127.0.0.1:${API_PORT}` },
    },
    'frontend'
  )
  await waitForHttp(`http://127.0.0.1:${WEB_PORT}/`, { label: 'vite', entry })
  return { log }
}

/**
 * fetch with one retry on a socket-level error.
 *
 * Node's fetch pools keep-alive connections. A long blocking step (spawnSync of
 * a python subprocess takes seconds) can outlive the server's idle timeout, so
 * the next request reuses a socket the server has already closed and fails with
 * ECONNRESET before reaching it. That looks exactly like the server having died,
 * so retry once rather than report a phantom failure.
 */
export async function fetchRetry(url, init) {
  try {
    return await fetch(url, init)
  } catch (e) {
    const code = e?.cause?.code
    if (code !== 'ECONNRESET' && code !== 'UND_ERR_SOCKET') throw e
    return await fetch(url, init)
  }
}

export function stopAll() {
  for (const { proc } of procs) {
    try {
      // Negative pid kills the whole group, reaching vite under npm.
      process.kill(-proc.pid, 'SIGKILL')
    } catch {
      try {
        proc.kill('SIGKILL')
      } catch {
        // already gone
      }
    }
  }
  procs.length = 0
}

// Ctrl-C would otherwise leak both servers and break the next run.
for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => {
    stopAll()
    process.exit(130)
  })
}

export function dumpLogs(name) {
  return procs
    .filter((p) => !name || p.name === name)
    .map((p) => `--- ${p.name} ---\n${p.log.join('')}`)
    .join('\n')
}

/**
 * Chromium flags that make a WebRTC app testable headlessly:
 * fake media devices so getUserMedia resolves without a prompt, and an
 * autoplay policy that lets AudioContext start without a user gesture.
 */
export const CHROMIUM_ARGS = [
  '--use-fake-device-for-media-stream',
  '--use-fake-ui-for-media-stream',
  '--autoplay-policy=no-user-gesture-required',
  '--enable-unsafe-swiftshader',
]
