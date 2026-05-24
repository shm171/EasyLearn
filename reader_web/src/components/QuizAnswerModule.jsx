import { useMemo, useState } from "react";
import { autocompletion, completeFromList } from "@codemirror/autocomplete";
import { python } from "@codemirror/lang-python";
import { EditorView } from "@codemirror/view";
import CodeMirror from "@uiw/react-codemirror";
import { CheckCircle2, Code2, Eye, RotateCcw } from "lucide-react";

const codeSnippets = [
  { label: "def", text: "def function_name():\n    pass" },
  { label: "for", text: "for item in items:\n    print(item)" },
  { label: "if", text: "if condition:\n    pass\nelse:\n    pass" },
  { label: "list", text: "numbers = [1, 2, 3]\nprint(numbers)" },
  { label: "input", text: "name = input(\"请输入：\")\nprint(name)" }
];

const completion = completeFromList([
  { label: "print", type: "function", apply: "print()" },
  { label: "input", type: "function", apply: "input()" },
  { label: "range", type: "function", apply: "range()" },
  { label: "len", type: "function", apply: "len()" },
  { label: "def", type: "keyword", apply: "def function_name():\n    pass" },
  { label: "for", type: "keyword", apply: "for item in items:\n    pass" },
  { label: "if", type: "keyword", apply: "if condition:\n    pass" },
  { label: "return", type: "keyword" },
  { label: "True", type: "constant" },
  { label: "False", type: "constant" }
]);

export default function QuizAnswerModule({ quiz }) {
  const [answers, setAnswers] = useState({});
  const [showAnswers, setShowAnswers] = useState(false);
  const questions = quiz.questions || [];
  const answeredCount = useMemo(
    () => questions.filter((question) => String(answers[question.question_id] || "").trim()).length,
    [answers, questions]
  );

  function updateAnswer(questionId, value) {
    setAnswers((current) => ({ ...current, [questionId]: value }));
  }

  function resetAnswers() {
    setAnswers({});
    setShowAnswers(false);
  }

  return (
    <section className="quiz-module">
      <div className="quiz-header">
        <div>
          <strong>答题练习</strong>
          <span>
            已答 {answeredCount} / {questions.length}
          </span>
        </div>
        <div className="quiz-actions">
          <button type="button" className="secondary-button" onClick={() => setShowAnswers((value) => !value)}>
            <Eye size={16} />
            <span>{showAnswers ? "隐藏答案" : "查看答案"}</span>
          </button>
          <button type="button" className="secondary-button" onClick={resetAnswers}>
            <RotateCcw size={16} />
            <span>清空</span>
          </button>
        </div>
      </div>

      {quiz.message ? <p className="quiz-message">{quiz.message}</p> : null}

      <div className="quiz-list">
        {questions.map((question, index) => (
          <QuestionCard
            key={question.question_id || index}
            index={index}
            question={normalizeQuestion(question, index)}
            answer={answers[question.question_id]}
            onAnswer={updateAnswer}
            showAnswer={showAnswers}
          />
        ))}
      </div>
    </section>
  );
}

function QuestionCard({ index, question, answer, onAnswer, showAnswer }) {
  const typeLabel = questionTypeLabel(question.question_type);

  return (
    <article className="quiz-card">
      <div className="quiz-card-head">
        <span className="quiz-number">Q{index + 1}</span>
        <span className="quiz-type">{typeLabel}</span>
        <span className="quiz-difficulty">{question.difficulty || "easy"}</span>
      </div>

      <div className="quiz-stem">{question.stem}</div>

      {question.code_snippet ? (
        <pre className="code-block quiz-snippet">
          <code>{question.code_snippet}</code>
        </pre>
      ) : null}

      {renderAnswerInput(question, answer || "", onAnswer)}

      {showAnswer ? (
        <div className="quiz-reference">
          <div>
            <CheckCircle2 size={16} />
            <strong>参考答案</strong>
          </div>
          <p>{stringifyAnswer(question.answer)}</p>
          {question.explanation ? <p className="quiz-explanation">{question.explanation}</p> : null}
        </div>
      ) : null}
    </article>
  );
}

function renderAnswerInput(question, answer, onAnswer) {
  const type = question.question_type;
  const options = buildOptions(question);

  if (options.length) {
    return (
      <div className="option-list">
        {options.map((option) => (
          <button
            type="button"
            key={option.value}
            className={`option-button${answer === option.value ? " selected" : ""}`}
            onClick={() => onAnswer(question.question_id, option.value)}
          >
            <span>{option.label}</span>
          </button>
        ))}
      </div>
    );
  }

  if (type === "fill_blank" || type === "short_answer") {
    return (
      <textarea
        className="quiz-text-answer"
        value={answer}
        onChange={(event) => onAnswer(question.question_id, event.target.value)}
        placeholder={type === "fill_blank" ? "在这里填写空缺内容..." : "写下你的简答..."}
      />
    );
  }

  if (type === "programming") {
    return (
      <div className="code-answer">
        <div className="snippet-bar">
          <Code2 size={16} />
          {codeSnippets.map((snippet) => (
            <button
              type="button"
              key={snippet.label}
              onClick={() => onAnswer(question.question_id, `${answer ? `${answer}\n` : ""}${snippet.text}`)}
            >
              {snippet.label}
            </button>
          ))}
        </div>
        <CodeMirror
          value={answer}
          height="220px"
          extensions={[python(), autocompletion({ override: [completion] }), EditorView.lineWrapping]}
          basicSetup={{
            lineNumbers: true,
            foldGutter: true,
            highlightActiveLine: true,
            autocompletion: true
          }}
          onChange={(value) => onAnswer(question.question_id, value)}
          placeholder="在这里写代码，输入 pri / for / def 会出现提示..."
        />
      </div>
    );
  }

  return (
    <textarea
      className="quiz-text-answer"
      value={answer}
      onChange={(event) => onAnswer(question.question_id, event.target.value)}
      placeholder="写下你的答案..."
    />
  );
}

function normalizeQuestion(question, index) {
  const questionId = question.question_id || `q${index + 1}`;
  return {
    ...question,
    question_id: questionId,
    question_type: question.question_type || "short_answer",
    stem: question.stem || question.question || "未命名题目"
  };
}

function buildOptions(question) {
  if (Array.isArray(question.options) && question.options.length) {
    return question.options.map((option, index) => {
      if (typeof option === "string") {
        return { label: option, value: option };
      }
      return {
        label: option.label || option.text || option.value || `选项 ${index + 1}`,
        value: option.value || option.label || option.text || String(index + 1)
      };
    });
  }
  if (question.question_type === "true_false") {
    return [
      { label: "正确", value: "true" },
      { label: "错误", value: "false" }
    ];
  }
  return [];
}

function questionTypeLabel(type) {
  return {
    true_false: "判断题",
    fill_blank: "填空题",
    programming: "编程题",
    short_answer: "简答题",
    single_choice: "选择题",
    multiple_choice: "选择题"
  }[type] || "练习题";
}

function stringifyAnswer(answer) {
  if (Array.isArray(answer)) {
    return answer.join("、");
  }
  return String(answer ?? "");
}
