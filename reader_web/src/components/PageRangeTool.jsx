import { useEffect, useState } from "react";
import { FileQuestion, ListChecks, MessageSquareText, Sparkles } from "lucide-react";
import {
  askRange,
  generateQuizFromRange,
  getKeyPointsFromRange,
  summarizeRange
} from "../api/client.js";

const taskOptions = [
  { value: "ask", label: "范围问答", icon: MessageSquareText },
  { value: "summary", label: "范围总结", icon: ListChecks },
  { value: "quiz", label: "范围出题", icon: FileQuestion },
  { value: "key-points", label: "提取重点", icon: Sparkles }
];

const questionTypes = [
  ["true_false", "判断题"],
  ["fill_blank", "填空题"],
  ["programming", "程序题"],
  ["short_answer", "简答题"]
];

export default function PageRangeTool({ courseId, currentPage = 1, totalPages = 0, onStart, onResult, onError }) {
  const [task, setTask] = useState("ask");
  const [pageStart, setPageStart] = useState(1);
  const [pageEnd, setPageEnd] = useState(1);
  const [question, setQuestion] = useState("这部分主要讲了什么？");
  const [language, setLanguage] = useState("python");
  const [difficulty, setDifficulty] = useState("easy");
  const [selectedTypes, setSelectedTypes] = useState(["true_false", "fill_blank"]);
  const [questionCount, setQuestionCount] = useState(5);

  useEffect(() => {
    if (currentPage) {
      setPageStart(currentPage);
      setPageEnd(currentPage);
    }
  }, [courseId]);

  async function submit(event) {
    event.preventDefault();
    const basePayload = {
      course_id: courseId,
      page_start: Number(pageStart),
      page_end: Number(pageEnd)
    };
    onStart(taskLabel(task));
    try {
      let result;
      if (task === "ask") {
        result = await askRange({ ...basePayload, question });
      } else if (task === "summary") {
        result = await summarizeRange(basePayload);
      } else if (task === "quiz") {
        result = await generateQuizFromRange({
          ...basePayload,
          programming_language: language,
          difficulty,
          question_types: selectedTypes,
          question_count: Number(questionCount)
        });
      } else {
        result = await getKeyPointsFromRange(basePayload);
      }
      onResult(result);
    } catch (error) {
      onError(error.message);
    }
  }

  function usePreset(type) {
    const total = totalPages || currentPage || 1;
    if (type === "current") {
      setPageStart(currentPage || 1);
      setPageEnd(currentPage || 1);
    } else if (type === "nearby") {
      setPageStart(Math.max(1, (currentPage || 1) - 2));
      setPageEnd(Math.min(total, (currentPage || 1) + 2));
    } else if (type === "chapter") {
      setPageStart(1);
      setPageEnd(total);
    }
  }

  function toggleType(type) {
    setSelectedTypes((current) => {
      if (current.includes(type)) {
        return current.length === 1 ? current : current.filter((item) => item !== type);
      }
      return [...current, type];
    });
  }

  return (
    <form className="range-tool" onSubmit={submit}>
      <div className="range-head">
        <strong>范围设置</strong>
        <span>{courseId || "未选择 course_id"}</span>
      </div>

      <div className="segmented">
        {taskOptions.map((option) => {
          const Icon = option.icon;
          return (
            <button
              key={option.value}
              type="button"
              className={task === option.value ? "active" : ""}
              onClick={() => setTask(option.value)}
            >
              <Icon size={16} />
              <span>{option.label}</span>
            </button>
          );
        })}
      </div>

      <div className="range-grid">
        <label>
          起始页
          <input
            type="number"
            min="1"
            max={totalPages || undefined}
            value={pageStart}
            onChange={(event) => setPageStart(event.target.value)}
          />
        </label>
        <label>
          结束页
          <input
            type="number"
            min="1"
            max={totalPages || undefined}
            value={pageEnd}
            onChange={(event) => setPageEnd(event.target.value)}
          />
        </label>
      </div>

      <div className="range-presets">
        <button type="button" onClick={() => usePreset("current")}>当前页</button>
        <button type="button" onClick={() => usePreset("nearby")}>前后 2 页</button>
        <button type="button" onClick={() => usePreset("chapter")} disabled={!totalPages}>全部页</button>
      </div>

      {task === "ask" ? (
        <label>
          问题
          <textarea value={question} onChange={(event) => setQuestion(event.target.value)} />
        </label>
      ) : null}

      {task === "quiz" ? (
        <div className="quiz-options">
          <div className="range-grid">
            <label>
              语言
              <input value={language} onChange={(event) => setLanguage(event.target.value)} />
            </label>
            <label>
              难度
              <select value={difficulty} onChange={(event) => setDifficulty(event.target.value)}>
                <option value="easy">easy</option>
                <option value="medium">medium</option>
                <option value="hard">hard</option>
                <option value="mixed">mixed</option>
              </select>
            </label>
          </div>
          <label>
            题目数
            <input
              type="number"
              min="1"
              max="50"
              value={questionCount}
              onChange={(event) => setQuestionCount(event.target.value)}
            />
          </label>
          <div className="checkbox-row">
            {questionTypes.map(([value, label]) => (
              <label key={value}>
                <input
                  type="checkbox"
                  checked={selectedTypes.includes(value)}
                  onChange={() => toggleType(value)}
                />
                {label}
              </label>
            ))}
          </div>
        </div>
      ) : null}

      <button type="submit" className="primary-button" disabled={!courseId}>
        发送到 AI 侧边栏
      </button>
    </form>
  );
}

function taskLabel(task) {
  return taskOptions.find((option) => option.value === task)?.label || "页码范围任务";
}
