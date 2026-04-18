/**
 * Riverst Live Demo Widget
 *
 * State machine: idle → auth_pending → [auth_rejected | connecting]
 *                → active → expiring → expired
 *                         ↘ error (from any active state)
 *
 * Auth flow: Google Identity Services → POST /api/auth/google → Riverst JWT
 * Session:   POST /api/session → POST /api/offer (Pipecat WebRTC) → TalkingHead
 */

import { PipecatClient, RTVIEvent } from '@pipecat-ai/client-js';
import { SmallWebRTCTransport } from '@pipecat-ai/small-webrtc-transport';

// ── Constants ─────────────────────────────────────────

const API_URL = import.meta.env.VITE_RIVERST_API_URL || 'http://localhost:7860';
const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || '';
const SESSION_DURATION_SECONDS = 300; // 5 minutes
const LIVE_DEMO_ENABLED = false; // set true to re-enable the interactive demo
const WARNING_THRESHOLD_SECONDS = 30;
const TOKEN_STORAGE_KEY = 'riverst_demo_token';

// ICE servers (matches RTVIProvider.tsx)
const ICE_SERVERS = [
  {
    urls: [
      'stun:stun.l.google.com:19302',
      'stun:stun.l.google.com:5349',
      'stun:stun1.l.google.com:3478',
      'stun:stun1.l.google.com:5349',
      'stun:stun2.l.google.com:19302',
      'stun:stun2.l.google.com:5349',
      'stun:stun3.l.google.com:3478',
      'stun:stun3.l.google.com:5349',
      'stun:stun4.l.google.com:19302',
      'stun:stun4.l.google.com:5349',
    ],
  },
];

// Session config for basic-avatar-demo.
// Must be flat — run_bot and TransportConfigurationManager read all fields
// directly from the top-level config dict (no options nesting).
const SESSION_CONFIG_DEFAULTS = {
  name: 'basic-avatar-demo',
  description: 'Basic avatar demo.',
  // Pipeline components (const in schema — hardcoded to openai)
  pipeline_modality: 'classic',
  stt_type: 'openai',
  llm_type: 'openai',
  tts_type: 'openai',
  // Behaviour
  advanced_flows: false,
  camera_settings: 'upper',
  task_description:
    'Demonstrate how you can interact with the user in a short conversation. Assist the user with their requests.',
  avatar_personality_description:
    "You are the 'River street' avatar, a friendly, helpful robot.",
  avatar_system_prompt:
    "You are an interactive robot. Keep your responses brief (one or two sentences at most). Your output will be converted to audio so don't include special characters in your answers. Respond to what the user said in a creative and helpful way. Start the conversation by introducing yourself.",
  body_animations: [
    'dance', 'wave', 'i_have_a_question', 'thank_you', 'i_dont_know',
    'ok', 'thumbup', 'thumbdown', 'happy', 'sad', 'angry', 'fear',
    'disgust', 'love', 'sleep', 'thinking',
  ],
  languages: ['english'],
  short_term_memory: false,
  long_term_memory: false,
  user_description: '',
  embodiment: 'humanoid_avatar',
  // Video / transport
  video_flag: true,
  video_out_width: 640,
  video_out_height: 320,
  video_out_framerate: 30,
  // Transcript display
  user_transcript: true,
  bot_transcript: true,
  // Avatar model
  avatar: {
    modelUrl: '/riverst/avatars/fabio_avaturn.glb',
    gender: 'masculine',
  },
};

// ── Widget Phase Enum ─────────────────────────────────

export const WidgetPhase = Object.freeze({
  idle: 'idle',
  auth_pending: 'auth_pending',
  auth_rejected: 'auth_rejected',
  connecting: 'connecting',
  active: 'active',
  expiring: 'expiring',
  expired: 'expired',
  error: 'error',
});

// ── State ─────────────────────────────────────────────

const state = {
  phase: WidgetPhase.idle,
  sessionId: null,
  remainingSeconds: SESSION_DURATION_SECONDS,
  errorMessage: null,
  authToken: null,
  userEmail: null,
  /** @type {PipecatClient|null} */
  pipecatClient: null,
  countdownInterval: null,
  /** @type {object|null} TalkingHead instance */
  talkingHead: null,
  /** true when we initiated the disconnect — suppresses the error state */
  intentionalDisconnect: false,
};

// ── DOM reference (populated by initWidget) ───────────

let containerEl = null;

// ── Valid state transitions ───────────────────────────

const TRANSITIONS = {
  [WidgetPhase.idle]: [WidgetPhase.auth_pending],
  [WidgetPhase.auth_pending]: [
    WidgetPhase.idle,
    WidgetPhase.auth_rejected,
    WidgetPhase.connecting,
  ],
  [WidgetPhase.auth_rejected]: [WidgetPhase.idle],
  [WidgetPhase.connecting]: [WidgetPhase.active, WidgetPhase.error],
  [WidgetPhase.active]: [WidgetPhase.expiring, WidgetPhase.error],
  [WidgetPhase.expiring]: [WidgetPhase.expired, WidgetPhase.error],
  [WidgetPhase.expired]: [WidgetPhase.idle],
  [WidgetPhase.error]: [WidgetPhase.idle],
};

// ── State Machine ─────────────────────────────────────

export function transitionTo(phase, extras = {}) {
  const allowed = TRANSITIONS[state.phase] || [];
  if (!allowed.includes(phase)) {
    console.warn(`[DemoWidget] Invalid transition: ${state.phase} → ${phase}`);
    return false;
  }
  state.phase = phase;
  if (extras.errorMessage !== undefined) state.errorMessage = extras.errorMessage;
  renderWidgetUI();
  return true;
}

// ── Google Identity Services ──────────────────────────

let gisLoaded = false;

function loadGIS() {
  return new Promise((resolve, reject) => {
    if (gisLoaded || window.google?.accounts?.id) {
      gisLoaded = true;
      resolve();
      return;
    }
    const script = document.createElement('script');
    script.src = 'https://accounts.google.com/gsi/client';
    script.async = true;
    script.defer = true;
    script.onload = () => {
      gisLoaded = true;
      resolve();
    };
    script.onerror = () => reject(new Error('Failed to load Google Identity Services'));
    document.head.appendChild(script);
  });
}

async function initGIS() {
  await loadGIS();
  window.google.accounts.id.initialize({
    client_id: GOOGLE_CLIENT_ID,
    callback: handleCredential,
    ux_mode: 'popup',
  });
}

export async function triggerAuth() {
  if (!LIVE_DEMO_ENABLED || state.phase !== WidgetPhase.idle) return;
  transitionTo(WidgetPhase.auth_pending); // renders UI with #demo-google-btn container
  try {
    await initGIS();
    // Use renderButton instead of prompt() — avoids One Tap cooldown/CORS issues
    // and works reliably on localhost. Credential still arrives via handleCredential.
    const btnContainer = document.getElementById('demo-google-btn');
    if (btnContainer) {
      window.google.accounts.id.renderButton(btnContainer, {
        type: 'standard',
        shape: 'pill',
        theme: 'outline',
        text: 'sign_in_with',
        size: 'large',
        width: 280,
      });
    }
  } catch (err) {
    console.error('[DemoWidget] GIS init failed:', err);
    transitionTo(WidgetPhase.error, {
      errorMessage: 'Failed to start sign-in. Please try again.',
    });
  }
}

// ── Auth: exchange Google credential for Riverst JWT ──

async function handleCredential(response) {
  try {
    const res = await fetch(`${API_URL}/api/auth/google`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: response.credential }),
    });

    if (res.status === 403) {
      transitionTo(WidgetPhase.auth_rejected);
      return;
    }

    if (!res.ok) {
      transitionTo(WidgetPhase.error, {
        errorMessage:
          res.status === 401
            ? 'Sign-in failed. Please try again.'
            : 'Authentication error. Please try again later.',
      });
      return;
    }

    const data = await res.json();
    const token = data.access_token;
    const email = data.user?.email || '';

    sessionStorage.setItem(TOKEN_STORAGE_KEY, token);
    state.authToken = token;
    state.userEmail = email;

    if (!transitionTo(WidgetPhase.connecting)) return;
    await createSession();
  } catch (err) {
    console.error('[DemoWidget] handleCredential error:', err);
    transitionTo(WidgetPhase.error, {
      errorMessage: 'Connection failed. Please try again.',
    });
  }
}

// ── Check stored token on page load ───────────────────

async function checkStoredToken() {
  const token = sessionStorage.getItem(TOKEN_STORAGE_KEY);
  if (!token) return;

  try {
    const res = await fetch(`${API_URL}/api/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok) {
      const data = await res.json();
      state.authToken = token;
      state.userEmail = data.email || '';
    } else {
      sessionStorage.removeItem(TOKEN_STORAGE_KEY);
    }
  } catch (_) {
    sessionStorage.removeItem(TOKEN_STORAGE_KEY);
  }
}

// ── Session Creation ──────────────────────────────────

async function createSession() {
  const payload = {
    ...SESSION_CONFIG_DEFAULTS,
    user_id: state.userEmail,
  };

  try {
    const res = await fetch(`${API_URL}/api/session`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${state.authToken}`,
      },
      body: JSON.stringify(payload),
    });

    if (res.status === 401) {
      sessionStorage.removeItem(TOKEN_STORAGE_KEY);
      transitionTo(WidgetPhase.error, {
        errorMessage: 'Session expired. Please sign in again.',
      });
      return;
    }

    if (!res.ok) {
      transitionTo(WidgetPhase.error, {
        errorMessage: 'Failed to start session. Please try again.',
      });
      return;
    }

    const data = await res.json();
    state.sessionId = data.session_id;
    await setupPipecat();
  } catch (err) {
    console.error('[DemoWidget] createSession error:', err);
    transitionTo(WidgetPhase.error, {
      errorMessage: 'Connection failed. Please try again.',
    });
  }
}

// ── Pipecat WebRTC Setup ──────────────────────────────

async function setupPipecat() {
  try {
    const transport = new SmallWebRTCTransport({
      webrtcUrl: `${API_URL}/api/offer?session_id=${encodeURIComponent(state.sessionId)}`,
      iceServers: ICE_SERVERS,
    });

    const client = new PipecatClient({
      transport,
      enableMic: true,
      callbacks: {
        onConnected: () => {
          if (!transitionTo(WidgetPhase.active)) return;
          mountTalkingHead();
          startCountdown();
        },
        onDisconnected: () => {
          // Ignore disconnect events we triggered ourselves
          if (state.intentionalDisconnect) return;
          if (
            state.phase === WidgetPhase.active ||
            state.phase === WidgetPhase.expiring
          ) {
            transitionTo(WidgetPhase.error, {
              errorMessage: 'Connection lost. Please try again.',
            });
          }
        },
        onError: (err) => {
          console.error('[DemoWidget] Pipecat error:', err);
          if (
            state.phase === WidgetPhase.connecting ||
            state.phase === WidgetPhase.active ||
            state.phase === WidgetPhase.expiring
          ) {
            transitionTo(WidgetPhase.error, {
              errorMessage: 'An error occurred with the live session.',
            });
          }
        },
        onTrackStarted: (track, participant) => {
          console.log('[DemoWidget] Track started:', track.kind, track.label || '(no label)', 'local:', participant?.local ?? '(no participant = remote)');
          // participant.local === true  → local mic captured by enableMic, skip
          // participant === undefined   → remote bot track from SmallWebRTCTransport
          if (track.kind !== 'audio' || participant?.local) return;
          // Play the bot's speech audio via a hidden <audio> element,
          // matching how PipecatClientAudio works in the React app.
          let audioEl = document.getElementById('demo-bot-audio');
          if (!audioEl) {
            audioEl = document.createElement('audio');
            audioEl.id = 'demo-bot-audio';
            audioEl.autoplay = true;
            document.body.appendChild(audioEl);
          }
          audioEl.srcObject = new MediaStream([track]);
          audioEl.play().catch((e) =>
            console.warn('[DemoWidget] Bot audio play failed:', e)
          );
        },
        onUserStartedSpeaking: () => {
          // Stop TalkingHead lip animation while the user is speaking
          state.talkingHead?.stopSpeaking?.();
        },
        onServerMessage: (msg) => {
          handleServerMessage(msg);
        },
      },
    });

    state.pipecatClient = client;
    await client.connect();
  } catch (err) {
    console.error('[DemoWidget] setupPipecat error:', err);
    transitionTo(WidgetPhase.error, {
      errorMessage: 'Failed to connect to avatar. Please try again.',
    });
  }
}

// ── Server Message Handler (animations / visemes) ─────

function handleServerMessage(msg) {
  console.log('[DemoWidget] Server message:', msg?.type, msg);
  const head = state.talkingHead;
  if (!head) return;

  if (msg.type === 'animation-event' && msg.payload?.animation_id) {
    playAnimation(head, msg.payload.animation_id, msg.payload.duration);
  } else if (msg.type === 'visemes-event' && msg.payload) {
    playVisemes(head, msg.payload);
  }
}

function playAnimation(head, animationId, duration) {
  const gestureMap = {
    wave: { gesture: 'handup', duration: 2 },
    dance: '/animations/dance/dance.fbx',
    i_have_a_question: 'index',
    thank_you: 'namaste',
    i_dont_know: 'shrug',
    ok: 'ok',
    thumbup: 'thumbup',
    thumbdown: 'thumbdown',
    thinking: '/animations/thinking/thinking.fbx',
  };
  const moodList = ['happy', 'angry', 'sad', 'fear', 'disgust', 'love', 'sleep'];
  const validExts = ['fbx', 'glb', 'gltf'];

  const val = gestureMap[animationId];
  if (val) {
    if (typeof val === 'string') {
      const ext = val.split('.').pop() || '';
      if (validExts.includes(ext)) {
        head.playAnimation?.(val, null, duration);
      } else {
        head.playGesture?.(val, duration);
      }
    } else if (typeof val === 'object') {
      head.playGesture?.(val.gesture, duration || val.duration);
    }
  } else if (moodList.includes(animationId)) {
    head.setMood?.(animationId);
    setTimeout(() => head.setMood?.('neutral'), duration ? duration * 1000 : 4000);
  }
}

function playVisemes(head, payload) {
  const { duration = 0 } = payload;
  if (duration <= 0) return;

  try {
    const dummyAudio = new AudioBuffer({
      length: Math.max(1, Math.ceil(duration * 16000)),
      sampleRate: 16000,
    });

    head.speakAudio?.({
      audio: dummyAudio,
      ...(payload.words && {
        words: payload.words,
        wtimes: payload.wtimes,
        wdurations: payload.wdurations,
      }),
      ...(payload.visemes && {
        visemes: payload.visemes,
        vtimes: payload.vtimes,
        vdurations: payload.vdurations,
      }),
    });
  } catch (err) {
    console.warn('[DemoWidget] playVisemes error:', err);
  }
}

// ── TalkingHead Avatar Mount ──────────────────────────

async function mountTalkingHead() {
  try {
    const mod = await import('./talkinghead/talkinghead.mjs');

    if (!containerEl) return;

    const head = new mod.TalkingHead(containerEl, {
      ttsEndpoint: 'N/A', // Audio comes via WebRTC; TH only handles viseme sync
      lipsyncModules: ['en'],
      cameraView: 'full',
      lightAmbientIntensity: 0,
      lightDirectIntensity: 0,
      lightDirectColor: '#fff',
    });

    await new Promise((resolve) => {
      head.showAvatar(
        {
          url: '/riverst/avatars/fabio_avaturn.glb',
          body: 'M',
          avatarMood: 'neutral',
          lipsyncLang: 'en',
        },
        resolve
      );
    });

    state.talkingHead = head;
  } catch (err) {
    console.error('[DemoWidget] TalkingHead mount error:', err);
    // Non-fatal: session continues even without avatar visual
  }
}

// ── Countdown Timer ───────────────────────────────────

function startCountdown() {
  state.remainingSeconds = SESSION_DURATION_SECONDS;

  state.countdownInterval = setInterval(async () => {
    state.remainingSeconds -= 1;
    updateCountdownDisplay();

    if (
      state.remainingSeconds <= WARNING_THRESHOLD_SECONDS &&
      state.phase === WidgetPhase.active
    ) {
      transitionTo(WidgetPhase.expiring);
    }

    if (state.remainingSeconds <= 0) {
      clearInterval(state.countdownInterval);
      state.countdownInterval = null;
      state.intentionalDisconnect = true;
      await endSession();
      transitionTo(WidgetPhase.expired);
    }
  }, 1000);
}

function updateCountdownDisplay() {
  const el = document.getElementById('demo-countdown');
  if (!el) return;

  const mins = Math.floor(state.remainingSeconds / 60);
  const secs = state.remainingSeconds % 60;
  el.textContent = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  el.hidden = false;
  el.classList.toggle('expiring', state.phase === WidgetPhase.expiring);
}

// ── End Session (user-initiated) ──────────────────────

async function handleEndSession() {
  state.intentionalDisconnect = true;
  await endSession();
  transitionTo(WidgetPhase.expired);
}

// ── End Session (cleanup) ─────────────────────────────

async function endSession() {
  if (!state.sessionId || !state.authToken) return;

  try {
    await fetch(`${API_URL}/api/end_session/${state.sessionId}`, {
      headers: { Authorization: `Bearer ${state.authToken}` },
    });
  } catch (err) {
    console.warn('[DemoWidget] endSession call failed (non-fatal):', err);
  }

  try {
    if (state.pipecatClient) {
      await state.pipecatClient.disconnect();
      state.pipecatClient = null;
    }
  } catch (_) {}

  try {
    if (state.talkingHead?.stop) {
      state.talkingHead.stop();
      state.talkingHead = null;
    }
  } catch (_) {}

  const audioEl = document.getElementById('demo-bot-audio');
  if (audioEl) {
    audioEl.srcObject = null;
    audioEl.remove();
  }
}

// ── beforeunload cleanup ──────────────────────────────

function registerUnloadHandler() {
  window.addEventListener('beforeunload', () => {
    if (state.sessionId && state.authToken) {
      fetch(`${API_URL}/api/end_session/${state.sessionId}`, {
        method: 'POST',
        keepalive: true,
        headers: { Authorization: `Bearer ${state.authToken}` },
      });
    }
  });
}

// ── Reset session state ───────────────────────────────

function resetSessionState() {
  if (state.countdownInterval) {
    clearInterval(state.countdownInterval);
    state.countdownInterval = null;
  }
  state.sessionId = null;
  state.remainingSeconds = SESSION_DURATION_SECONDS;
  state.errorMessage = null;
  state.pipecatClient = null;
  state.talkingHead = null;
  state.intentionalDisconnect = false;

  const controls = document.getElementById('demo-session-controls');
  if (controls) controls.hidden = true;

  const countdown = document.getElementById('demo-countdown');
  if (countdown) countdown.classList.remove('expiring');
}

// ── HTML escape ───────────────────────────────────────

function escapeHtml(str) {
  if (typeof str !== 'string') return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// ── Render Widget UI ──────────────────────────────────

export function renderWidgetUI() {
  const statusEl = document.getElementById('demo-status');
  const idleEl = document.getElementById('widget-idle');
  const canvasContainer = document.getElementById('talkinghead-canvas-container');
  const ctaBtn = document.getElementById('demo-cta-btn');

  if (!statusEl) return;

  statusEl.innerHTML = '';

  const showCanvas = (show) => {
    if (canvasContainer) canvasContainer.hidden = !show;
  };

  switch (state.phase) {
    case WidgetPhase.idle:
      resetSessionState();
      showCanvas(false);
      if (LIVE_DEMO_ENABLED) {
        if (idleEl) idleEl.hidden = false;
        statusEl.innerHTML = '';
      }
      // When disabled, static HTML in #demo-status already shows Coming Soon.
      break;

    case WidgetPhase.auth_pending:
      if (idleEl) idleEl.hidden = true;
      showCanvas(false);
      statusEl.innerHTML = `
        <div class="widget-state">
          <p>Sign in with Google to start the live demo</p>
          <div id="demo-google-btn" style="margin-top:16px;display:flex;justify-content:center"></div>
          <p style="font-size:0.75rem;color:var(--text-muted,#6b7280);margin-top:12px">
            Your session will last 5 minutes.
          </p>
        </div>`;
      break;

    case WidgetPhase.auth_rejected:
      if (idleEl) idleEl.hidden = true;
      showCanvas(false);
      statusEl.innerHTML = `
        <div class="widget-message" role="alert">
          <div class="widget-message-icon" aria-hidden="true">🔒</div>
          <p class="widget-message-title">Demo Access by Invitation</p>
          <p class="widget-message-text">
            Live demo access is currently limited to authorized accounts.
            Watch our videos to see Riverst in action.
          </p>
          <div style="display:flex;gap:12px;flex-wrap:wrap;justify-content:center">
            <a href="#demo-videos" class="btn btn-primary">Watch Videos</a>
            <button type="button" class="btn btn-ghost" id="widget-retry-btn">Try a Different Account</button>
          </div>
        </div>`;
      document.getElementById('widget-retry-btn')?.addEventListener('click', handleRetry);
      break;

    case WidgetPhase.connecting:
      if (idleEl) idleEl.hidden = true;
      showCanvas(false);
      statusEl.innerHTML = `
        <div class="widget-state">
          <div class="widget-spinner" role="status" aria-label="Connecting to avatar"></div>
          <p>Connecting to avatar&hellip;</p>
        </div>`;
      break;

    case WidgetPhase.active:
    case WidgetPhase.expiring: {
      if (idleEl) idleEl.hidden = true;
      showCanvas(true);
      const controls = document.getElementById('demo-session-controls');
      if (controls) controls.hidden = false;
      updateCountdownDisplay();
      break;
    }

    case WidgetPhase.expired:
      if (idleEl) idleEl.hidden = true;
      showCanvas(false);
      statusEl.innerHTML = `
        <div class="widget-message" role="status">
          <div class="widget-message-icon" aria-hidden="true">🎉</div>
          <p class="widget-message-title">Thanks for trying Riverst!</p>
          <p class="widget-message-text">
            Your 5-minute demo session has ended.
            Watch the full demos or deploy your own instance.
          </p>
          <div style="display:flex;gap:12px;flex-wrap:wrap;justify-content:center">
            <a href="#demo-videos" class="btn btn-primary">Watch Videos</a>
            <a href="#get-started" class="btn btn-secondary">Deploy Your Own</a>
            <button type="button" class="btn btn-ghost" id="widget-retry-btn">Try Again</button>
          </div>
        </div>`;
      document.getElementById('widget-retry-btn')?.addEventListener('click', handleRetry);
      break;

    case WidgetPhase.error: {
      if (idleEl) idleEl.hidden = true;
      showCanvas(false);
      const msg = state.errorMessage || 'Something went wrong. Please try again.';
      statusEl.innerHTML = `
        <div class="widget-message" role="alert">
          <div class="widget-message-icon" aria-hidden="true">⚠️</div>
          <p class="widget-message-title">Something went wrong</p>
          <p class="widget-message-text">${escapeHtml(msg)}</p>
          <div style="display:flex;gap:12px;flex-wrap:wrap;justify-content:center">
            <a href="#demo-videos" class="btn btn-secondary">Watch Videos</a>
            <button type="button" class="btn btn-primary" id="widget-retry-btn">Try Again</button>
          </div>
        </div>`;
      document.getElementById('widget-retry-btn')?.addEventListener('click', handleRetry);
      break;
    }
  }

  // Show/hide the CTA button (never shown when live demo is disabled)
  if (ctaBtn) ctaBtn.hidden = !LIVE_DEMO_ENABLED || state.phase !== WidgetPhase.idle;
}

// ── Retry ─────────────────────────────────────────────

function handleRetry() {
  endSession().catch(() => {});
  state.authToken = null;
  state.userEmail = null;
  state.phase = WidgetPhase.idle; // force-reset; bypass transition guard
  renderWidgetUI();
}

// ── Init ──────────────────────────────────────────────

export function initWidget(el) {
  containerEl = el;

  // Guard: WebRTC availability
  if (typeof RTCPeerConnection === 'undefined') {
    const statusEl = document.getElementById('demo-status');
    const idleEl = document.getElementById('widget-idle');
    if (idleEl) idleEl.hidden = true;
    if (statusEl) {
      statusEl.innerHTML = `
        <div class="browser-notice" role="alert">
          <p><strong>Live demo requires WebRTC support.</strong></p>
          <p style="margin-top:8px">Please use Chrome, Firefox, Safari 15+, or Edge.</p>
          <a href="#demo-videos" class="btn btn-primary" style="margin-top:16px">Watch Videos Instead</a>
        </div>`;
    }
    return;
  }

  document.getElementById('demo-end-btn')?.addEventListener('click', () => {
    handleEndSession().catch(() => {});
  });

  registerUnloadHandler();
  checkStoredToken();
  renderWidgetUI();
}
