import React, { useEffect, useState, useRef } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import axios from "axios";
import { Pagination, FloatButton, Tooltip } from "antd";
import { SettingOutlined, SoundOutlined, FileTextOutlined, HighlightOutlined } from "@ant-design/icons";
import "antd/dist/reset.css";

const AudioPlayerPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const book = searchParams.get("book");
  const chapter = searchParams.get("chapter");
  const [data, setData] = useState<any>({});
  const [loading, setLoading] = useState(false);
  const [current, setCurrent] = useState(1); // 1-based index for Pagination

  // Helper to parse boolean flags from URL params
  const getFlag = (param: string, defaultValue = true) => {
    const val = searchParams.get(param);
    if (val === null) return defaultValue;
    if (val === "true") return true;
    if (val === "false") return false;
    return defaultValue;
  };

  // Flags state
  const [audioFlag, setAudioFlag] = useState<boolean>(getFlag("audio_flag", true));
  const [textFlag, setTextFlag] = useState<boolean>(getFlag("text_flag", true));
  const [subtitlesFlag, setSubtitlesFlag] = useState<boolean>(() => {
    const base = getFlag("subtitles_flag", true);
    return (getFlag("audio_flag", true) && getFlag("text_flag", true)) ? base : false;
  });
  const [settingsFlag, _] = useState<boolean>(getFlag("settings_flag", true));

  // Enforce subtitlesFlag logic: can only be true if both audioFlag and textFlag are true
  useEffect(() => {
    if (!(audioFlag && textFlag) && subtitlesFlag) {
      setSubtitlesFlag(false);
    }
  }, [audioFlag, textFlag]);

  // Compute error directly from current flag values
  const error =
    !audioFlag && !textFlag
      ? "At least one of audio or text must be enabled."
      : null;

  useEffect(() => {
    if (!book || !chapter) {
      navigate("/error", {
        state: {
          message: "Missing required parameters: book and chapter.",
          status: 500,
        },
      });
      return;
    }
    setLoading(true);
    axios
      .get("/api/audiobook_info", {
        params: { book, chapter },
      })
      .then((res) => {
        setData(res.data);
      })
      .catch((err) => {
        if (err.response?.status === 404) {
          navigate("/error", {
            state: {
              message: "Audiobook not found. Please try again.",
              status: 404,
            },
          });
        } else {
          setData({});
        }
      })
      .finally(() => setLoading(false));
  }, [book, chapter]);

  return (
    <div style={{ textAlign: "left", padding: "2rem 2rem 5% 5%", position: "relative" }}>
      <h1 style={{ marginBottom: "0" }}>{data && data.title}</h1>
      <p>{data && data.author}</p>
      <h2>{data && data.chapthersCount} - {data && data.chapterTitle}</h2>
      {loading ? (
        <div>Loading...</div>
      ) : error ? (
        <div style={{ color: "red" }}>{error}</div>
      ) : data && data.chapters && data.chapters.length > 0 ? (
        <div style={{ padding: "0 0 2rem 0" }}>
          <AudioPlayer
            audio_flag={audioFlag}
            text_flag={textFlag}
            subtitles_flag={subtitlesFlag}
            key={current}
            link={data.chapters[current - 1]?.link}
            start={data.chapters[current - 1]?.start}
            end={data.chapters[current - 1]?.end}
            words={data.chapters[current - 1]?.text}
          />
          {data.chapters.length > 1 && (
            <Pagination
              current={current}
              pageSize={1}
              total={data.chapters.length}
              onChange={setCurrent}
              style={{ marginBottom: 24, marginTop: 24 }}
              showSizeChanger={false}
              align="center"
            />
          )}
        </div>
      ) : null}

      {settingsFlag && (
        <FloatButton.Group
          trigger="click"
          type="primary"
          style={{ right: 24, bottom: 24, position: "fixed" }}
          icon={<SettingOutlined />}
        >
          <Tooltip title="Audio">
            <FloatButton
              icon={<SoundOutlined />}
              type={audioFlag ? "primary" : "default"}
              onClick={() => setAudioFlag((prev) => !prev)}
            />
          </Tooltip>
          <Tooltip title="Text">
            <FloatButton
              icon={<FileTextOutlined />}
              type={textFlag ? "primary" : "default"}
              onClick={() => setTextFlag((prev) => !prev)}
            />
          </Tooltip>
          { audioFlag && textFlag && (
            <Tooltip title="Subtitles (voice-over)">
              <FloatButton
                icon={<HighlightOutlined />}
                type={subtitlesFlag ? "primary" : "default"}
                onClick={() => {
                  // Only allow enabling if both audio and text are true
                  if (audioFlag && textFlag) {
                    setSubtitlesFlag((prev) => !prev);
                  }
                  // else do nothing (button is visually "disabled" by type and tooltip)
                }}
              />
            </Tooltip>
          )}
        </FloatButton.Group>
      )}
    </div>
  );
};

const AudioPlayer: React.FC<{
  audio_flag: boolean;
  text_flag: boolean;
  subtitles_flag: boolean;
  link: string;
  start: number | null;
  end: number | null;
  words?: { start: number | null; end: number | null; text: string }[];
}> = ({ audio_flag, text_flag, subtitles_flag, link, start, end, words }) => {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [audioDuration, setAudioDuration] = useState<number | null>(null);
  const [currentTime, setCurrentTime] = useState<number>(0);

  // Set start and end defaults
  const effectiveStart = start != null ? start : 0;
  const effectiveEnd = end != null ? end : audioDuration;

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    // Seek to start time when loaded
    const handleLoadedMetadata = () => {
      setAudioDuration(audio.duration);
      audio.currentTime = effectiveStart;
    };
    audio.addEventListener("loadedmetadata", handleLoadedMetadata);
    return () => {
      audio.removeEventListener("loadedmetadata", handleLoadedMetadata);
    };
    // eslint-disable-next-line
  }, [link, start, end]);

  // Restrict playback to [start, end]
  const handleTimeUpdate = () => {
    const audio = audioRef.current;
    if (!audio) return;
    setCurrentTime(audio.currentTime);
    if (effectiveEnd != null && audio.currentTime > effectiveEnd) {
      audio.pause();
      audio.currentTime = effectiveEnd;
    }
  };

  // If user seeks before start, jump to start
  const handleSeeking = () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (audio.currentTime < effectiveStart) {
      audio.currentTime = effectiveStart;
    }
    if (effectiveEnd != null && audio.currentTime > effectiveEnd) {
      audio.currentTime = effectiveEnd;
    }
  };

  // Find the index of the word to highlight
  let highlightedIdx: number | null = null;
  if (subtitles_flag && words && Array.isArray(words)) {
    highlightedIdx = words.findIndex(
      (w) =>
        w.start != null &&
        w.end != null &&
        currentTime >= w.start &&
        currentTime < w.end
    );
  }

  return (
    <div>
      {audio_flag && (
        <audio
          ref={audioRef}
          src={link}
          controls
          style={{ width: "100%" }}
          onTimeUpdate={handleTimeUpdate}
          onSeeking={handleSeeking}
        />
      )}
      {text_flag && words && Array.isArray(words) && words.length > 0 && (
        <div style={{ marginTop: 16, fontSize: 20, lineHeight: 1.5, wordBreak: "break-word" }}>
          {words.map((w, i) => (
            <span
              key={i}
              style={{
                background: subtitles_flag && i === highlightedIdx ? "#ffe066" : undefined,
                borderRadius: 4,
                transition: "background 0.2s",
                cursor: w.start != null ? "pointer" : undefined
              }}
              onClick={() => {
                if (audioRef.current && w.start != null) {
                  audioRef.current.currentTime = w.start;
                  audioRef.current.play();
                }
              }}
            >
              {w.text + " "}
            </span>
          ))}
        </div>
      )}
    </div>
  );
};

export default AudioPlayerPage;
