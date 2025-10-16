import React, { useState } from "react";
import { Collapse, Table, Typography, message, Button } from "antd";
import { ArrowLeftOutlined, PlayCircleFilled, CopyFilled } from '@ant-design/icons';
import { useNavigate } from "react-router-dom";

const { Panel } = Collapse;
const { Text } = Typography;


import { Switch } from "antd";
import FullPageLoader from "../components/FullPageLoader";

const ListenToAudioBookPage: React.FC = () => {
  const [books, setBooks] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [_, setCopying] = useState<string | null>(null);
  // State for flags per chapter row: { [rowKey]: { settings_flag, audio_flag, text_flag, subtitles_flag } }
  const [flags, setFlags] = useState<{ [key: string]: any }>({});
  const navigate = useNavigate();

  // Fetch books data from server
  React.useEffect(() => {
    const fetchBooks = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch("/api/audiobooks");
        if (!res.ok) throw new Error("Failed to fetch audiobooks");
        const data = await res.json();
        setBooks(data);
      } catch (err: any) {
        setError(err.message || "Unknown error");
      } finally {
        setLoading(false);
      }
    };
    fetchBooks();
  }, []);

  // Initialize flags for all chapters if not already set
  React.useEffect(() => {
    const initialFlags: { [key: string]: any } = {};
    books.forEach((book) => {
      book.chapters.forEach((chapter: any) => {
        if (!flags[chapter.key]) {
          initialFlags[chapter.key] = {
            settings_flag: true,
            audio_flag: true,
            text_flag: true,
            subtitles_flag: true,
          };
        }
      });
    });
    if (Object.keys(initialFlags).length > 0) {
      setFlags((prev) => ({ ...initialFlags, ...prev }));
    }
    // eslint-disable-next-line
  }, [books]);

  const handleToggle = (rowKey: string, flag: string, value: boolean) => {
    setFlags((prev: any) => {
      const prevRow = prev[rowKey] || {};
      let newRow = { ...prevRow, [flag]: value };

      // Enforce logic: audio_flag and text_flag cannot both be false
      if (flag === "audio_flag" && !value && !prevRow.text_flag) {
        newRow.text_flag = true;
      }
      if (flag === "text_flag" && !value && !prevRow.audio_flag) {
        newRow.audio_flag = true;
      }
      // If audio or text is false, subtitles cannot be true
      if (
        (flag === "audio_flag" && !value && prevRow.subtitles_flag) ||
        (flag === "text_flag" && !value && prevRow.subtitles_flag)
      ) {
        newRow.subtitles_flag = false;
      }
      if (
        flag === "subtitles_flag" &&
        value &&
        (!newRow.audio_flag || !newRow.text_flag)
      ) {
        // Can't enable subtitle if audio or text is false
        return prev;
      }
      return { ...prev, [rowKey]: newRow };
    });
  };

  // Centralized function to generate the activity link
  const getActivityLink = (chapter: any) => {
    const rowFlags = flags[chapter.key] || {
      settings_flag: true,
      audio_flag: true,
      text_flag: true,
      subtitles_flag: true,
    };
    const params = new URLSearchParams({
      book: chapter.bookKey,
      chapter: String(chapter.key),
    });
    // Only add flags if they are false
    if (rowFlags.settings_flag === false) params.set("settings_flag", "false");
    if (rowFlags.audio_flag === false) params.set("audio_flag", "false");
    if (rowFlags.text_flag === false) params.set("text_flag", "false");
    if (rowFlags.text_flag === true && rowFlags.audio_flag === true && rowFlags.subtitles_flag === false) params.set("subtitles_flag", "false");

    return `/audio-player?${params.toString()}`;
  };

  const handleCopy = async (chapter: any) => {
    const link = getActivityLink(chapter);
    try {
      setCopying(chapter.key);
      await navigator.clipboard.writeText(
        window.location.origin + link
      );
      message.success("Link copied to clipboard!");
    } catch (err) {
      message.error("Failed to copy link.");
    } finally {
      setCopying(null);
    }
  };

  if (loading) {
    return <FullPageLoader />;
  }

  if (error) {
    return (
      <div style={{ padding: 24 }}>
        <h1>Listen to an audiobook</h1>
        <p style={{ color: "red" }}>Error: {error}</p>
      </div>
    );
  }

  return (
    <div
      style={{
        margin: "0 auto",
        padding: "24px 24px 48px",
        width: "100%",
        boxSizing: "border-box",
      }}
    >
      <Button
        icon={<ArrowLeftOutlined />}
        onClick={() => navigate('/')}
        type="default"
        style={{ marginBottom: '0.5rem', marginTop: '1rem' }}
      >
        Back
      </Button>

      <h1>Listen to an audiobook</h1>
      <p>Pick a book and chapter to read/listen plus some settings. Then, you can copy the link and share it with others or play it directly on this device. </p>
      <Collapse accordion defaultActiveKey={books[0]?.key}>
        {books.map((book) => (
          <Panel header={book.title} key={book.key}>
            <div style={{ width: "100%", overflowX: "auto" }}>
              <Table
                dataSource={book.chapters}
                rowKey="key"
                pagination={false}
                scroll={{ x: "max-content" }}
                columns={[
                  {
                    title: "Chapter",
                    dataIndex: "chapterTitle",
                    key: "chapterTitle",
                    render: (text: string) => <Text>{text}</Text>,
                    width: 200,
                  },
                  {
                    title: "Settings",
                    key: "settings_flag",
                    render: (_: any, record: any) => (
                      <Switch
                        checked={flags[record.key]?.settings_flag ?? true}
                        onChange={(val) =>
                          handleToggle(record.key, "settings_flag", val)
                        }
                      />
                    ),
                    align: "center" as const,
                  },
                  {
                    title: "Audio support",
                    key: "audio_flag",
                    render: (_: any, record: any) => (
                      <Switch
                        checked={flags[record.key]?.audio_flag ?? true}
                        onChange={(val) =>
                          handleToggle(record.key, "audio_flag", val)
                        }
                      />
                    ),
                    align: "center" as const,
                  },
                  {
                    title: "Text support",
                    key: "text_flag",
                    render: (_: any, record: any) => (
                      <Switch
                        checked={flags[record.key]?.text_flag ?? true}
                        onChange={(val) =>
                          handleToggle(record.key, "text_flag", val)
                        }
                      />
                    ),
                    align: "center" as const,
                  },
                  {
                    title: "Subtitles",
                    key: "subtitles_flag",
                    render: (_: any, record: any) => (
                      <Switch
                        checked={flags[record.key]?.subtitles_flag ?? true}
                        onChange={(val) =>
                          handleToggle(record.key, "subtitles_flag", val)
                        }
                        disabled={
                          !(
                            (flags[record.key]?.audio_flag ?? true) &&
                            (flags[record.key]?.text_flag ?? true)
                          )
                        }
                      />
                    ),
                    align: "center" as const,
                  },
                  {
                    title: "Play",
                    key: "play",
                    render: (_: any, record: any) => {
                      const link = getActivityLink(record);
                      return (
                        <Button
                          type="primary"
                          onClick={() => navigate(link)}
                          size="small"
                          icon={<PlayCircleFilled />}
                        />
                      );
                    },
                    align: "center" as const,
                  },
                  {
                    title: "Link",
                    key: "copy",
                    render: (_: any, record: any) => (
                      <Button
                        type="primary"
                        onClick={() => handleCopy(record)}
                        size="small"
                        icon={<CopyFilled />}
                      />
                    ),
                    align: "center" as const,
                  },
                ]}
              />
            </div>
          </Panel>
        ))}
      </Collapse>
    </div>
  );
};

export default ListenToAudioBookPage;
