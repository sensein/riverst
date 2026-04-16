import './style.css';
import { activities } from './content/activities.js';
import { videos } from './content/videos.js';
import { background } from './content/background.js';
import { team } from './content/team.js';

// ── Sticky Nav: highlight active section on scroll ────

function initStickyNav() {
  const navLinks = document.querySelectorAll('.nav-link[href^="#"]');
  const sections = document.querySelectorAll('section[id]');

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          const id = entry.target.getAttribute('id');
          navLinks.forEach((link) => {
            const isActive = link.getAttribute('href') === `#${id}`;
            link.classList.toggle('active', isActive);
          });
        }
      });
    },
    {
      rootMargin: `-${getNavHeight()}px 0px -60% 0px`,
      threshold: 0,
    }
  );

  sections.forEach((section) => observer.observe(section));
}

function getNavHeight() {
  const header = document.querySelector('.site-header');
  return header ? header.offsetHeight : 64;
}

// ── Hamburger menu toggle ─────────────────────────────

function initHamburger() {
  const btn = document.querySelector('.nav-hamburger');
  const links = document.getElementById('nav-links');
  if (!btn || !links) return;

  btn.addEventListener('click', () => {
    const isOpen = links.classList.toggle('open');
    btn.setAttribute('aria-expanded', String(isOpen));
  });

  // Close on nav link click (mobile)
  links.querySelectorAll('.nav-link').forEach((link) => {
    link.addEventListener('click', () => {
      links.classList.remove('open');
      btn.setAttribute('aria-expanded', 'false');
    });
  });

  // Close on outside click
  document.addEventListener('click', (e) => {
    if (!btn.contains(e.target) && !links.contains(e.target)) {
      links.classList.remove('open');
      btn.setAttribute('aria-expanded', 'false');
    }
  });
}

// ── Hero Section ─────────────────────────────────────

function renderHero() {
  const section = document.getElementById('hero');
  if (!section) return;

  section.innerHTML = `
    <div class="hero-inner">
      <img
        src="/riverst/logo/riverst_black.svg"
        alt="Riverst"
        class="hero-logo"
        width="200"
        height="56"
      />
      <h1 id="hero-heading" class="hero-heading">
        Build. Run. Analyze.
      </h1>
      <p class="hero-tagline">
        An open-source platform for interactive user–avatar conversations,
        powered by real-time AI voice and WebRTC.
      </p>
      <div class="hero-ctas">
        <a href="#demo" class="btn btn-primary btn-large" id="hero-demo-cta">
          Watch Demo
        </a>
        <button
          id="hero-try-live"
          class="btn btn-secondary btn-large"
          type="button"
        >
          Try Live Demo
        </button>
        <a
          href="https://github.com/sensein/riverst"
          class="btn btn-ghost btn-large"
          target="_blank"
          rel="noopener noreferrer"
          aria-label="View Riverst on GitHub (opens in new tab)"
        >
          View on GitHub
        </a>
      </div>
      <div class="hero-screenshot">
        <img
          src="/riverst/screenshots/fabio_says_hi.png"
          alt="A Riverst avatar session in progress — the Fabio avatar speaks to a user via WebRTC in a browser-based interface"
          width="800"
          loading="eager"
        />
      </div>
    </div>
  `;

  // Wire "Try Live Demo" hero button to scroll to #demo and trigger the widget
  const heroDemoBtn = document.getElementById('hero-try-live');
  if (heroDemoBtn) {
    heroDemoBtn.addEventListener('click', () => {
      const demoSection = document.getElementById('demo');
      if (demoSection) {
        demoSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
      // Give scroll time to complete, then trigger widget
      setTimeout(() => {
        const demoCta = document.getElementById('demo-cta-btn');
        if (demoCta && !demoCta.hidden) demoCta.click();
      }, 600);
    });
  }
}

// ── Background Section ────────────────────────────────

export function renderBackground() {
  const container = document.getElementById('background-content');
  if (!container) return;

  const paragraphsHtml = background.paragraphs
    .map((p) => `<p>${escapeHtml(p)}</p>`)
    .join('');

  let citationsHtml = '';
  if (background.citations && background.citations.length > 0) {
    const items = background.citations
      .map((c) => `<li><a href="${escapeHtml(c.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(c.text)}</a></li>`)
      .join('');
    citationsHtml = `
      <div class="background-citations">
        <p class="background-citations-title">References</p>
        <ol>${items}</ol>
      </div>
    `;
  }

  container.innerHTML = paragraphsHtml + citationsHtml;
}

// ── Activities Section ────────────────────────────────

export function renderActivities() {
  const grid = document.getElementById('activities-grid');
  if (!grid) return;

  grid.innerHTML = activities
    .map(
      (activity) => `
      <article class="activity-card" role="listitem">
        <div class="activity-icon" aria-hidden="true">${activity.icon}</div>
        <h3 class="activity-title">${escapeHtml(activity.title)}</h3>
        <p class="activity-description">${escapeHtml(activity.description)}</p>
        <div class="activity-tags" aria-label="Tags">
          ${activity.tags.map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join('')}
        </div>
      </article>
    `
    )
    .join('');
}

// ── Videos Section ────────────────────────────────────

export function renderVideos() {
  const grid = document.getElementById('video-grid');
  if (!grid) return;

  grid.innerHTML = videos
    .map((video, index) => {
      const isPlaceholder = !video.youtubeId || video.youtubeId === 'PLACEHOLDER';
      const screenshotImages = [
        '/riverst/screenshots/fabio_says_hi.png',
        '/riverst/screenshots/session_summary_example.png',
        '/riverst/screenshots/automated_audio_analysis.png',
      ];
      const posterSrc = video.posterUrl || screenshotImages[index] || screenshotImages[0];

      if (isPlaceholder) {
        return `
          <div class="video-item" role="listitem">
            <div class="video-wrapper">
              <div class="video-placeholder" aria-label="${escapeHtml(video.title)} — coming soon">
                <div class="video-placeholder-icon" aria-hidden="true">▶️</div>
                <p class="video-placeholder-label">Coming soon</p>
              </div>
              <img
                class="video-poster"
                src="${escapeHtml(posterSrc)}"
                alt=""
                aria-hidden="true"
                style="opacity:0.25"
              />
            </div>
            <p class="video-title">${escapeHtml(video.title)}</p>
            <p class="video-description">${escapeHtml(video.description)}</p>
          </div>
        `;
      }

      return `
        <div class="video-item" role="listitem">
          <div class="video-wrapper">
            <img
              class="video-poster"
              src="${escapeHtml(posterSrc)}"
              alt=""
              aria-hidden="true"
            />
            <iframe
              src="https://www.youtube.com/embed/${encodeURIComponent(video.youtubeId)}"
              title="${escapeHtml(video.title)}"
              loading="lazy"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowfullscreen
            ></iframe>
          </div>
          <p class="video-title">${escapeHtml(video.title)}</p>
          <p class="video-description">${escapeHtml(video.description)}</p>
        </div>
      `;
    })
    .join('');

  // Fade in iframes on load, hide poster
  grid.querySelectorAll('.video-wrapper iframe').forEach((iframe) => {
    iframe.addEventListener('load', () => {
      iframe.classList.add('loaded');
      const poster = iframe.previousElementSibling;
      if (poster && poster.classList.contains('video-poster')) {
        poster.style.opacity = '0';
      }
    });
  });
}

// ── Team Section ──────────────────────────────────────

export function renderTeam() {
  const grid = document.getElementById('team-grid');
  if (!grid) return;

  grid.innerHTML = team
    .map(
      (member) => `
      <article class="team-card" role="listitem">
        ${
          member.photoUrl
            ? `<img
                class="team-photo"
                src="${escapeHtml(import.meta.env.BASE_URL + member.photoUrl.replace(/^\//, ''))}"
                alt="Photo of ${escapeHtml(member.name)}"
                width="96"
                height="96"
                loading="lazy"
              />`
            : `<div class="team-photo-placeholder" role="img" aria-label="${escapeHtml(member.name)} — no photo available">👤</div>`
        }
        <p class="team-name">${escapeHtml(member.name)}</p>
        <p class="team-role">${escapeHtml(member.role)}</p>
        <p class="team-institution">${escapeHtml(member.institution)}</p>
        ${
          member.profileLink
            ? `<a
                href="${escapeHtml(member.profileLink)}"
                class="team-link"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="View ${escapeHtml(member.name)}'s profile (opens in new tab)"
              >View Profile</a>`
            : ''
        }
      </article>
    `
    )
    .join('');
}

// ── Utility: HTML escape ──────────────────────────────

function escapeHtml(str) {
  if (typeof str !== 'string') return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// ── Demo Widget Wiring ────────────────────────────────

async function initDemoWidget() {
  try {
    const { initWidget, triggerAuth } = await import('./demo-widget.js');
    const container = document.getElementById('talkinghead-canvas-container');
    if (container) initWidget(container);

    const ctaBtn = document.getElementById('demo-cta-btn');
    if (ctaBtn) {
      ctaBtn.addEventListener('click', () => {
        triggerAuth();
      });
    }
  } catch (err) {
    console.error('Failed to load demo widget:', err);
  }
}

// ── Boot ──────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  renderHero();
  renderBackground();
  renderActivities();
  renderVideos();
  renderTeam();
  initStickyNav();
  initHamburger();
  initDemoWidget();
});
