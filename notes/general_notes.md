# Voice, Agents, and Lip-Sync Notes

This document organizes references, apps, and observations related to voice synthesis, real-time agents, and avatar systems. Feel free to open PRs with more resources you think others may appreciate while working with Riverst.

---

## 📈 Industry insights & discussions on stt+llm+tts pipeline vs e2e model
- [Andrew Ng: The Voice Stack (LinkedIn post)](https://www.linkedin.com/posts/andrewyng_the-voice-stack-is-improving-rapidly-systems-activity-7300912040959778818-B_hc/) — overview of the evolving voice tech stack.
- [LinkedIn post on voice/avatars](https://www.linkedin.com/feed/update/urn:li:activity:7306294278815633408/) — industry perspective on avatar/voice progress.
- [Realtime AI Agents Frameworks (Medium)](https://medium.com/@ggarciabernardo/realtime-ai-agents-frameworks-bb466ccb2a09) — comparison of frameworks for live AI agents.

## 📈 Our insights & discussions on stt+llm+tts pipeline vs e2e model
- Currently unreliable: poor at function calling, not Pipecat-compatible, inconsistent transcripts.
- Known issues: [Pipecat issue #1781](https://github.com/pipecat-ai/pipecat/issues/1781), [Gemini Live invalid payload](https://discuss.ai.google.dev/t/received-1007-invalid-payload-using-gemini-live-api/83206/11).
- Faster than pipeline-based approaches, but not recommended for production yet.

---

## 🧑‍🤝‍🧑 Related apps & avatars
- [Dollyglot](https://www.dollyglot.com/) — fun F2F interactions.
- [Talkie AI](https://www.talkie-ai.com/it) — practice speaking scenarios (text-based).
- [Character.ai](https://character.ai/) — conversational app (weak avatar/emotion support).
- [Fluently](https://getfluently.app/) — app for improving English speaking skills.
- [Replika](https://replika.com/) — AI companion, limited emotion/avatar control ([demo](https://my.replika.com/)).

---

## 🛠️ Frameworks & Tools
- [Ultravox Docs](https://docs.ultravox.ai/) — potential alternative to Pipecat.

### 🎙️ Full-duplex discussions/alternatives
- [Sesame: Crossing the Uncanny Valley of Voice (demo)](https://www.sesame.com/research/crossing_the_uncanny_valley_of_voice#demo) — research demo on natural synthetic voices.
- [Full-duplex architecture (paper)](https://arxiv.org/pdf/2405.19487) — architectures enabling simultaneous speech input/output.

---

## 🎥 Related research projects
- [TalkingHead demo (YouTube)](https://www.youtube.com/watch?v=Hv-ItCZ0qc4) — study showcasing expressive avatars.
