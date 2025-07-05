import React, {
  useEffect,
  useRef,
  forwardRef,
  useImperativeHandle,
} from "react";
import { KokoroTTS } from "../../../kokorotts.mjs";

const TTS_BASE_URL = `ws://localhost:7860/tts-proxy/`; // local proxy

let TTSSocket: WebSocket | null = null;
let TTSOutput: any = null;


export async function kokoroSpeak(
  kokoro: any,
  kokoroQueue: any[],
  head: any,
  text: string,
  getSentenceId: () => number,
  incrementSentenceId: () => void,
  onsubtitles: (sentence: string, id: number, word: string) => void,
) {
  const dividers = { "! ": 1, ". ": 1, "? ": 1 };
  const maxLen = 500;
  const letters = [...text];
  const items: any[] = [];

  let lastSpace = 0;
  let sentence = "";

  for (let i = 0; i < letters.length; i++) {
    const isLast = i === letters.length - 1;
    const letter = letters[i];
    const letterTwo = isLast ? null : letter + letters[i + 1];
    const isDivider = isLast ? false : dividers.hasOwnProperty(letterTwo);
    const isMax = i === maxLen;

    if (letter === " ") lastSpace = i;
    sentence += letter;

    let s = null;
    if (isMax) {
      if (lastSpace === 0) lastSpace = i;
      s = sentence.slice(0, lastSpace).trim();
      sentence = sentence.slice(lastSpace + 1);
    } else if (isLast || isDivider) {
      s = sentence.trim();
      sentence = "";
    }

    if (s) {
      const item = { text: s, onsubtitles, status: 0 };
      items.push(item);
      kokoroQueue.push(item);
    }
  }

  for (let i = 0; i < items.length; i++) {
    const item = items[i];
    kokoro.generate(item.text, async (data: any) => {
      data.audio = await head.audioCtx.decodeAudioData(data.audio);
      item.audio = data;
      item.status = 1;
      processKokoroQueue(kokoroQueue, head, getSentenceId, incrementSentenceId);
    });
  }
}

function processKokoroQueue(
  queue: any[],
  head: any,
  getSentenceId: () => number,
  incrementSentenceId: () => void
) {
  while (queue.length) {
    const item = queue[0];
    if (item.status === 0) break;
    queue.shift();
    if (item.audio) {
      try {
        const sentenceId = getSentenceId();
        head.speakAudio(
          item.audio,
          {},
          item.onsubtitles?.bind(null, item.text.slice(), sentenceId)
        );
        incrementSentenceId();
      } catch (e) {
        console.error("Kokoro speak error:", e);
      }
    }
  }
}


export async function TTSspeak(head: any, text: string, lipsyncLang = "en", sessionId: string) {
  if (!text) return;

  if (!TTSSocket || TTSSocket.readyState > 1) {
    TTSSocket = new WebSocket(TTS_BASE_URL + sessionId);

    TTSSocket.onopen = () => {
      TTSSocket!.send(JSON.stringify({ text }));
    };

    TTSSocket.onmessage = (event) => {
      const r = JSON.parse(event.data);

      if ((r.isFinal || r.normalizedAlignment) && TTSOutput) {
        head.speakAudio(TTSOutput, { lipsyncLang });
        TTSOutput = null;
      }

      if (!r.isFinal) {
        if (r.alignment) {
          TTSOutput = {
            audio: [],
            words: [],
            wtimes: [],
            wdurations: [],
          };

          let word = "",
            t0 = 0,
            dur = 0;
          r.alignment.chars.forEach((ch: string, i: number) => {
            if (!word) t0 = r.alignment.charStartTimesMs[i];
            if (ch === " ") {
              if (word) {
                TTSOutput.words.push(word);
                TTSOutput.wtimes.push(t0);
                TTSOutput.wdurations.push(dur);
              }
              word = "";
              dur = 0;
            } else {
              word += ch;
              dur += r.alignment.charDurationsMs[i];
            }
          });
          if (word) {
            TTSOutput.words.push(word);
            TTSOutput.wtimes.push(t0);
            TTSOutput.wdurations.push(dur);
          }
        }

        if (r.audio && TTSOutput) {
          TTSOutput.audio.push(head.b64ToArrayBuffer(r.audio));
        }
      }
    };

    TTSSocket.onerror = (e) => {
      console.error("TTS WS error", e);
      TTSSocket?.close();
      TTSSocket = null;
    };

    TTSSocket.onclose = () => (TTSSocket = null);
  } else {
    if (TTSSocket.readyState === 1) {
      TTSSocket.send(JSON.stringify({ text }));
    }
  }
}


/* ------------------------------------------------------------------ */
/*                          REACT COMPONENT                           */
/* ------------------------------------------------------------------ */

interface Props {
  cameraType: "full" | "mid" | "upper" | "head";
  interactionState?: "speaking" | "listening" | null;
  utterance?: string | null;
  avatar: { id: number; modelUrl: string; gender: string };
  height: number;
  width: number;
  animation: string | null;
  onAvatarMounted?: () => void;
  sessionId: string;
  ttsType: string;
  subtitleFlag: boolean;
  addSubtitle: (text: string, speaker: string) => void;
}

const TalkingHeadWrapper = forwardRef<any, Props>((props, ref) => {
  const {
    cameraType,
    interactionState,
    utterance,
    avatar,
    height,
    width,
    animation,
    onAvatarMounted,
    sessionId,
    ttsType,
    subtitleFlag,
    addSubtitle,
  } = props;

  const divRef = useRef<HTMLDivElement>(null);
  const headRef = useRef<any>(null);
  const readyRef = useRef(false);

  useImperativeHandle(ref, () => headRef.current, []);

  /* -------------------------------------------------- mount avatar */
  useEffect(() => {
    let isMounted = true;

    import("../../../talkinghead.mjs").then((mod) => {
      if (!isMounted || !divRef.current) return;

      const head = new mod.TalkingHead(divRef.current, {
        ttsEndpoint: TTS_BASE_URL + sessionId,
        lipsyncModules: ["en"],
        cameraView: "full",
        lightAmbientIntensity: 0,
        lightDirectIntensity: 0,
        lightDirectColor: "#000",
      });

      const body = avatar.gender === "feminine" ? "F" : "M";

      head.showAvatar(
        {
          url: avatar.modelUrl,
          body,
          avatarMood: "neutral",
          lipsyncLang: "en",
        },
        () => {}
      );

      setTimeout(() => head.setView(cameraType), 1500);

      headRef.current = head;
      readyRef.current = true;
      onAvatarMounted?.();
    });

    return () => {
      isMounted = false;
      if (headRef.current?.stop) headRef.current.stop();
      headRef.current = null;
      /* close TTS socket if open */
      if (TTSSocket?.readyState === 1) TTSSocket.close();
    };
  }, [avatar, cameraType]);

  /* -------------------------------------------------- kokoro TTS */
  const voice_id =
    avatar.gender === "feminine"
      ? "af_bella" // feminine voice
      : "am_puck"; // masculine voice
  const kokoroRef = useRef(new KokoroTTS({ voice: voice_id, speed: 1, language: "en-us" }));
  const kokoroQueue = useRef<any[]>([]);
  const kokoroSentenceId = useRef(0);

  useEffect(() => {
    kokoroRef.current.load();
  }, []);

  /* ------------------------------------------------ speech effect */
  useEffect(() => {
    if (!utterance || !readyRef.current) return;
    if (ttsType === "kokoro") {
      console.log("[KOKORO] Speaking:", utterance);
      const head = headRef.current;
      kokoroSpeak(
        kokoroRef.current,
        kokoroQueue.current,
        head,
        utterance,
        () => kokoroSentenceId.current,
        () => kokoroSentenceId.current++,
        (sentence, id, word) => {
          console.log(`[KOKORO] ${sentence} [${id}] -> ${word}`);
          if (subtitleFlag) {
            addSubtitle(sentence, 'bot');
          }
        }
      );
    } else {
      console.log("[TTS] Speaking:", utterance);
      if (subtitleFlag) {
        addSubtitle(utterance, 'bot');
      }
      TTSspeak(headRef.current, utterance, "en", sessionId);
      TTSspeak(headRef.current, ".", "en", sessionId); // to trigger lipsync for the last sentence
    }
  }, [utterance]);

  /* ------------------------------------------------ state effect */
  useEffect(() => {
    const head = headRef.current;
    if (!head) return;

    if (interactionState === "listening") {
      head.stopSpeaking();
    } else if (interactionState !== "speaking") {
      head.setMood("neutral");
    }
  }, [interactionState]);

  /* ---------------------------------------------- animation effect */
  useEffect(() => {
    const head = headRef.current;
    if (!head) return;

    switch (animation) {
      case "wave":
        head.playGesture("handup", 2);
        break;
      case "dance":
        head.playPose("/animations/dance/dance.fbx");
        break;
      case 'i_have_a_question':
        head.playGesture('index');
        break;
      case 'thank_you':
        head.playGesture('namaste');
        break;
      case 'i_dont_know':
        head.playGesture('shrug');
        break;
      case 'ok':
      case 'thumbup':
      case 'thumbdown':
        head.playGesture(animation);
        break;
      case "happy":
      case "angry":
      case "sad":
      case "fear":
      case "disgust":
      case "love":
      case "sleep":
        head.setMood(animation);
        setTimeout(() => head.setMood("neutral"), 4000);
        break;
      default:
    }
  }, [animation]);

  /* ------------------------------------------------------- render */
  return (
    <div
      ref={divRef}
      style={{
        width: `${width}%`,
        height: `${height}vh`,
        background: "#BAE0FF1A",
        overflow: "hidden",
      }}
    />
  );
});

export default TalkingHeadWrapper;
