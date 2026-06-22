(function(){const e=document.createElement("link").relList;if(e&&e.supports&&e.supports("modulepreload"))return;for(const i of document.querySelectorAll('link[rel="modulepreload"]'))r(i);new MutationObserver(i=>{for(const o of i)if(o.type==="childList")for(const s of o.addedNodes)s.tagName==="LINK"&&s.rel==="modulepreload"&&r(s)}).observe(document,{childList:!0,subtree:!0});function n(i){const o={};return i.integrity&&(o.integrity=i.integrity),i.referrerPolicy&&(o.referrerPolicy=i.referrerPolicy),i.crossOrigin==="use-credentials"?o.credentials="include":i.crossOrigin==="anonymous"?o.credentials="omit":o.credentials="same-origin",o}function r(i){if(i.ep)return;i.ep=!0;const o=n(i);fetch(i.href,o)}})();const p=[{id:"playground",title:"Free-Style Interaction",description:"Open-ended conversation with an AI avatar — no script, no curriculum. Perfect for exploring what Riverst can do.",icon:"🗣️",tags:["Playground","Open-ended"]},{id:"kiva-vocab",title:"KIVA Vocabulary Learning",description:"Children discover new words through fun, guided play with an avatar. Part of the KIVA (Knowledge Integration and Vocabulary Acquisition) research program.",icon:"📚",tags:["Education","Children","Vocabulary"]},{id:"audiobook",title:"Audiobook Companion",description:"Follow along with an audiobook while an avatar provides visual cues and comprehension support that goes beyond just listening.",icon:"🎧",tags:["Reading","Comprehension"]},{id:"esl-vocab",title:"English for Italian Speakers",description:"Guided vocabulary acquisition for Italian speakers learning English — powered by a patient, interactive avatar tutor.",icon:"🇺🇸",tags:["Language Learning","ESL"]},{id:"isl-vocab",title:"Italian for English Speakers",description:"Guided vocabulary acquisition for English speakers learning Italian — powered by a patient, interactive avatar tutor.",icon:"🇮🇹",tags:["Language Learning","Italian"]}],l={tagline:"KIVA (Knowledge Integration and Vocabulary Accelerator) uses Riverst to help young learners build academic vocabulary through natural conversations with an AI avatar. Watch the pitch to learn more.",pitchVideo:{youtubeId:"LMfxs7uhNnE",title:"KIVA Project Pitch"}},c={youtubeId:"PodFCwsoq8w",title:"KIVA in Action",description:"Watch a live KIVA vocabulary tutoring session — an avatar helping a child learn academic vocabulary through natural conversation."},u=[{id:"team-member-1",name:"Satrajit Ghosh",role:"Principal Investigator",institution:"Massachusetts Institute of Technology",photoUrl:"/team/satra_about_photo.png",profileLink:"https://satra.cogitatum.org/"},{id:"team-member-2",name:"Ola Ozernov-Palchik",role:"Principal Investigator",institution:"Boston University",photoUrl:"/team/ola_about_photo.jpg",profileLink:"https://www.bu.edu/wheelock/profile/ola-ozernov-palchik/"},{id:"team-member-3",name:"Fabio Catania",role:"Postdoctoral Associate",institution:"Now at Apple",photoUrl:"/team/fabio_catania_about_photo.jpg",profileLink:null},{id:"team-member-4",name:"Jordan Wilke",role:"Technical Associate",institution:"Massachusetts Institute of Technology",photoUrl:"/team/jordan_wilke_about_photo.jpeg",profileLink:null}];function g(){const t=document.querySelectorAll('.nav-link[href^="#"]'),e=document.querySelectorAll("section[id]"),n=new IntersectionObserver(r=>{r.forEach(i=>{if(i.isIntersecting){const o=i.target.getAttribute("id");t.forEach(s=>{const d=s.getAttribute("href")===`#${o}`;s.classList.toggle("active",d)})}})},{rootMargin:`-${h()}px 0px -60% 0px`,threshold:0});e.forEach(r=>n.observe(r))}function h(){const t=document.querySelector(".site-header");return t?t.offsetHeight:64}function m(){const t=document.querySelector(".nav-hamburger"),e=document.getElementById("nav-links");!t||!e||(t.addEventListener("click",()=>{const n=e.classList.toggle("open");t.setAttribute("aria-expanded",String(n))}),e.querySelectorAll(".nav-link").forEach(n=>{n.addEventListener("click",()=>{e.classList.remove("open"),t.setAttribute("aria-expanded","false")})}),document.addEventListener("click",n=>{!t.contains(n.target)&&!e.contains(n.target)&&(e.classList.remove("open"),t.setAttribute("aria-expanded","false"))}))}function v(){const t=document.getElementById("hero");t&&(t.innerHTML=`
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
  `)}function f(){const t=document.getElementById("kiva-content");if(!t)return;t.innerHTML=`
    <p class="section-intro">${a(l.tagline)}</p>
    <div class="kiva-video-wrapper">
      <iframe
        src="https://www.youtube.com/embed/${encodeURIComponent(l.pitchVideo.youtubeId)}"
        title="${a(l.pitchVideo.title)}"
        loading="lazy"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        sandbox="allow-scripts allow-same-origin allow-presentation allow-popups"
        allowfullscreen
      ></iframe>
    </div>
  `;const e=t.querySelector(".kiva-video-wrapper iframe");e&&e.addEventListener("load",()=>e.classList.add("loaded"))}function b(){const t=document.getElementById("activities-grid");t&&(t.innerHTML=p.map(e=>`
      <article class="activity-card" role="listitem">
        <div class="activity-icon" aria-hidden="true">${e.icon}</div>
        <h3 class="activity-title">${a(e.title)}</h3>
        <p class="activity-description">${a(e.description)}</p>
        <div class="activity-tags" aria-label="Tags">
          ${e.tags.map(n=>`<span class="tag">${a(n)}</span>`).join("")}
        </div>
      </article>
    `).join(""))}function y(){const t=document.getElementById("demo-video-container");if(!t)return;t.innerHTML=`
    <div class="demo-video-wrapper">
      <iframe
        src="https://www.youtube.com/embed/${encodeURIComponent(c.youtubeId)}"
        title="${a(c.title)}"
        loading="lazy"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        sandbox="allow-scripts allow-same-origin allow-presentation allow-popups"
        allowfullscreen
      ></iframe>
    </div>
    <p class="demo-video-description">${a(c.description)}</p>
  `;const e=t.querySelector("iframe");e&&e.addEventListener("load",()=>e.classList.add("loaded"))}function w(){const t=document.getElementById("team-grid");t&&(t.innerHTML=u.map(e=>`
      <article class="team-card" role="listitem">
        ${e.photoUrl?`<img
                class="team-photo"
                src="${a("/riverst/"+e.photoUrl.replace(/^\//,""))}"
                alt="Photo of ${a(e.name)}"
                width="96"
                height="96"
                loading="lazy"
              />`:`<div class="team-photo-placeholder" role="img" aria-label="${a(e.name)} — no photo available">👤</div>`}
        <p class="team-name">${a(e.name)}</p>
        <p class="team-role">${a(e.role)}</p>
        <p class="team-institution">${a(e.institution)}</p>
        ${e.profileLink?`<a
                href="${a(e.profileLink)}"
                class="team-link"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="View ${a(e.name)}'s profile (opens in new tab)"
              >View Profile</a>`:""}
      </article>
    `).join(""))}function a(t){return typeof t!="string"?"":t.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;")}document.addEventListener("DOMContentLoaded",()=>{v(),f(),b(),y(),w(),g(),m()});
