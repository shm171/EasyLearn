import { memo, useCallback, useMemo, useState } from "react";
import { autocompletion, completeFromList, startCompletion } from "@codemirror/autocomplete";
import { python } from "@codemirror/lang-python";
import { EditorView } from "@codemirror/view";
import CodeMirror from "@uiw/react-codemirror";
import { AlertCircle, CheckCircle2, ClipboardCheck, Eye, Loader2, RotateCcw, XCircle } from "lucide-react";
import { evaluateQuiz } from "../api/client.js";

const genericCompletions = [
  { label: "for", type: "keyword" },
  { label: "while", type: "keyword" },
  { label: "if", type: "keyword" },
  { label: "else", type: "keyword" },
  { label: "return", type: "keyword" },
  { label: "class", type: "keyword" },
  { label: "function", type: "keyword" },
  { label: "main", type: "function" },
  { label: "true", type: "constant" },
  { label: "false", type: "constant" }
];

const languageCompletions = {
  python: [
    { label: "def", type: "keyword" },
    { label: "elif", type: "keyword" },
    { label: "in", type: "keyword" },
    { label: "import", type: "keyword" },
    { label: "print", type: "function", apply: "print()" },
    { label: "input", type: "function", apply: "input()" },
    { label: "range", type: "function", apply: "range()" },
    { label: "len", type: "function", apply: "len()" },
    { label: "int", type: "function", apply: "int()" },
    { label: "random.randint", type: "function", apply: "random.randint()" },
    { label: "None", type: "constant" },
    { label: "True", type: "constant" },
    { label: "False", type: "constant" }
  ],
  javascript: [
    { label: "const", type: "keyword" },
    { label: "let", type: "keyword" },
    { label: "console.log", type: "function", apply: "console.log()" },
    { label: "document.querySelector", type: "function", apply: "document.querySelector()" }
  ],
  java: [
    { label: "public", type: "keyword" },
    { label: "static", type: "keyword" },
    { label: "void", type: "keyword" },
    { label: "String", type: "type" },
    { label: "System.out.println", type: "function", apply: "System.out.println()" }
  ],
  cpp: [
    { label: "#include", type: "keyword" },
    { label: "std::cout", type: "function" },
    { label: "std::cin", type: "function" },
    { label: "vector", type: "type" },
    { label: "string", type: "type" }
  ]
};

const triggerCompletionAfterPaste = EditorView.updateListener.of((update) => {
  if (update.docChanged && update.transactions.some((transaction) => transaction.isUserEvent("input.paste"))) {
    window.setTimeout(() => startCompletion(update.view), 0);
  }
});
const codeExtensionCache = new Map();

export default function QuizAnswerModule({ quiz }) {
  const [answers, setAnswers] = useState({});
  const [showAnswers, setShowAnswers] = useState(false);
  const [grading, setGrading] = useState(false);
  const [gradeError, setGradeError] = useState("");
  const [evaluation, setEvaluation] = useState(null);
  const questions = useMemo(() => (quiz.questions || []).map(normalizeQuestion), [quiz.questions]);
  const gradeResults = useMemo(() => buildGradeResultMap(evaluation), [evaluation]);
  const codeLanguage = quiz.programming_language || quiz.language || "";
  const answeredCount = useMemo(
    () => questions.filter((question) => String(answers[question.question_id] || "").trim()).length,
    [answers, questions]
  );

  const updateAnswer = useCallback((questionId, value) => {
    setGradeError("");
    setEvaluation(null);
    setAnswers((current) => ({ ...current, [questionId]: value }));
  }, []);

  function resetAnswers() {
    setAnswers({});
    setShowAnswers(false);
    setGradeError("");
    setEvaluation(null);
  }

  async function gradeAnswers() {
    if (!questions.length) {
      return;
    }
    if (!answeredCount) {
      setGradeError("请先至少完成一道题，再提交批改。");
      return;
    }
    setGrading(true);
    setGradeError("");
    setEvaluation(null);
    try {
      const payload = buildEvaluationPayload(quiz, questions, answers);
      setEvaluation(await evaluateQuiz(payload));
    } catch (error) {
      setGradeError(cleanErrorMessage(error));
    } finally {
      setGrading(false);
    }
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
          <button type="button" className="primary-button compact-button" onClick={gradeAnswers} disabled={grading}>
            {grading ? <Loader2 size={16} className="spin" /> : <ClipboardCheck size={16} />}
            <span>{grading ? "批改中" : "批改"}</span>
          </button>
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
      {gradeError ? (
        <div className="quiz-grade-error">
          <AlertCircle size={16} />
          <span>{gradeError}</span>
        </div>
      ) : null}
      {evaluation ? <EvaluationSummary evaluation={evaluation} /> : null}

      <div className="quiz-list">
        {questions.map((question, index) => (
          <QuestionCard
            key={question.question_id || index}
            index={index}
            question={question}
            answer={answers[question.question_id]}
            onAnswer={updateAnswer}
            showAnswer={showAnswers}
            gradeResult={gradeResults.get(question.question_id)}
            codeLanguage={codeLanguage}
          />
        ))}
      </div>
    </section>
  );
}

function EvaluationSummary({ evaluation }) {
  const results = evaluation.question_results || [];
  const correctCount = results.filter((item) => item.is_correct).length;
  return (
    <div className="quiz-grade-summary">
      <div>
        <strong>{Math.round(Number(evaluation.total_score || 0))} 分</strong>
        <span>
          正确 {correctCount} / {results.length}
        </span>
      </div>
      {evaluation.weakness_summary ? <p>{evaluation.weakness_summary}</p> : null}
    </div>
  );
}

const QuestionCard = memo(function QuestionCard({ index, question, answer, onAnswer, showAnswer, gradeResult, codeLanguage }) {
  const typeLabel = questionTypeLabel(question.question_type);
  const inferredCodeLanguage = useMemo(
    () => inferCodeLanguage(codeLanguage, question, answer),
    [answer, codeLanguage, question]
  );

  return (
    <article className="quiz-card">
      <div className="quiz-card-head">
        <span className="quiz-number">Q{index + 1}</span>
        <span className="quiz-type">{typeLabel}</span>
        <span className="quiz-difficulty">{question.difficulty || "easy"}</span>
        {gradeResult ? (
          <span className={`quiz-score ${gradeResult.is_correct ? "correct" : "wrong"}`}>
            {Math.round(Number(gradeResult.score || 0))} 分
          </span>
        ) : null}
      </div>

      <div className="quiz-stem">{question.stem}</div>

      {question.code_snippet ? (
        <pre className="code-block quiz-snippet">
          <code>{question.code_snippet}</code>
        </pre>
      ) : null}

      {renderAnswerInput(question, answer || "", onAnswer, inferredCodeLanguage)}
      {gradeResult ? <QuestionFeedback result={gradeResult} /> : null}

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
});

function QuestionFeedback({ result }) {
  return (
    <div className={`quiz-feedback ${result.is_correct ? "correct" : "wrong"}`}>
      <div>
        {result.is_correct ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
        <strong>{result.is_correct ? "回答正确" : "需要修正"}</strong>
      </div>
      {result.feedback ? <p>{result.feedback}</p> : null}
      {result.correct_answer ? <p>参考：{result.correct_answer}</p> : null}
      {result.explanation ? <p>{result.explanation}</p> : null}
    </div>
  );
}

function renderAnswerInput(question, answer, onAnswer, codeLanguage) {
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
        <CodeMirror
          value={answer}
          height="220px"
          extensions={codeExtensions(codeLanguage)}
          basicSetup={{
            lineNumbers: true,
            foldGutter: true,
            highlightActiveLine: true,
            autocompletion: true
          }}
          onChange={(value) => onAnswer(question.question_id, value)}
          placeholder="在这里写代码或解题思路，按 Ctrl+Space 查看提示..."
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

function codeExtensions(language) {
  const normalizedLanguage = normalizeCodeLanguage(language);
  if (codeExtensionCache.has(normalizedLanguage)) {
    return codeExtensionCache.get(normalizedLanguage);
  }
  const completion = completeFromList([
    ...genericCompletions,
    ...(languageCompletions[normalizedLanguage] || [])
  ]);
  const baseExtensions = [
    autocompletion({ override: [completion], activateOnTyping: true }),
    triggerCompletionAfterPaste,
    EditorView.lineWrapping
  ];
  if (normalizedLanguage === "python") {
    const extensions = [python(), ...baseExtensions];
    codeExtensionCache.set(normalizedLanguage, extensions);
    return extensions;
  }
  codeExtensionCache.set(normalizedLanguage, baseExtensions);
  return baseExtensions;
}

function inferCodeLanguage(baseLanguage, question, answer) {
  const text = [
    baseLanguage,
    question?.programming_language,
    question?.language,
    question?.stem,
    question?.code_snippet,
    question?.answer,
    answer
  ]
    .filter(Boolean)
    .join("\n")
    .toLowerCase();

  if (/\bpython\b|\bdef\s+\w+\s*\(|\bimport\s+\w+|print\s*\(|input\s*\(|range\s*\(|random\.randint|\bnone\b|\belif\b/.test(text)) {
    return "python";
  }
  if (/\bjavascript\b|\bjs\b|console\.log|\bconst\s+|\blet\s+|=>/.test(text)) {
    return "javascript";
  }
  if (/\bc\+\+\b|\bcpp\b|#include|std::|cout\s*<<|cin\s*>>/.test(text)) {
    return "cpp";
  }
  if (/\bjava\b|system\.out\.println|public\s+static\s+void\s+main/.test(text)) {
    return "java";
  }
  return "text";
}

function normalizeCodeLanguage(language) {
  const lowered = String(language || "").toLowerCase();
  if (lowered.includes("python")) {
    return "python";
  }
  if (lowered.includes("javascript") || lowered === "js") {
    return "javascript";
  }
  if (lowered.includes("c++") || lowered.includes("cpp")) {
    return "cpp";
  }
  if (lowered.includes("java")) {
    return "java";
  }
  return "text";
}

function normalizeQuestion(question, index = 0) {
  const questionId = String(question.question_id ?? question.id ?? `q${index + 1}`);
  return {
    ...question,
    question_id: questionId,
    question_type: question.question_type || "short_answer",
    stem: question.stem || question.question || "未命名题目",
    difficulty: normalizeConcreteDifficulty(question.difficulty)
  };
}

function buildOptions(question) {
  if (Array.isArray(question.options) && question.options.length) {
    return question.options.map((option, index) => {
      if (typeof option === "string") {
        return {
          label: option,
          value: question.question_type === "true_false" ? trueFalseValue(option, index) : option
        };
      }
      return {
        label: option.label || option.text || option.value || `选项 ${index + 1}`,
        value:
          question.question_type === "true_false"
            ? trueFalseValue(option.value || option.label || option.text, index)
            : option.value || option.label || option.text || String(index + 1)
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

function buildGradeResultMap(evaluation) {
  const results = evaluation?.question_results || [];
  return new Map(results.map((result) => [String(result.question_id), result]));
}

function buildEvaluationPayload(quiz, questions, answers) {
  return {
    quiz: {
      quiz_id: String(quiz.quiz_id || `reader_quiz_${Date.now()}`),
      course_id: String(quiz.course_id || "reader_local"),
      chapter_title: String(quiz.chapter_title || quiz.quiz_title || "资料阅读器练习"),
      programming_language: String(quiz.programming_language || quiz.language || "text"),
      difficulty: normalizeQuizDifficulty(quiz.difficulty),
      questions: questions.map((question, index) => ({
        question_id: String(question.question_id || `q${index + 1}`),
        question_type: normalizeQuestionType(question.question_type, question.options),
        stem: question.stem || question.question || `题目 ${index + 1}`,
        options: normalizeOptionsForSchema(question.options),
        code_snippet: question.code_snippet || null,
        answer: stringifyAnswer(question.answer),
        explanation: question.explanation || "",
        difficulty: normalizeConcreteDifficulty(question.difficulty),
        knowledge_points: Array.isArray(question.knowledge_points) ? question.knowledge_points : [],
        reference_chunks: Array.isArray(question.reference_chunks) ? question.reference_chunks : []
      }))
    },
    user_answers: questions.map((question) => ({
      question_id: String(question.question_id),
      answer: String(answers[question.question_id] || "")
    }))
  };
}

function normalizeQuestionType(type, options) {
  if (["true_false", "fill_blank", "programming", "short_answer"].includes(type)) {
    return type;
  }
  if (Array.isArray(options) && options.length) {
    return "short_answer";
  }
  return "short_answer";
}

function normalizeQuizDifficulty(difficulty) {
  return ["easy", "medium", "hard", "mixed"].includes(difficulty) ? difficulty : "mixed";
}

function normalizeConcreteDifficulty(difficulty) {
  return ["easy", "medium", "hard"].includes(difficulty) ? difficulty : "easy";
}

function normalizeOptionsForSchema(options) {
  if (!Array.isArray(options) || !options.length) {
    return null;
  }
  return options.map((option, index) => {
    if (typeof option === "string") {
      return option;
    }
    return String(option.label || option.text || option.value || `选项 ${index + 1}`);
  });
}

function cleanErrorMessage(error) {
  const message = error?.message || String(error || "批改失败");
  try {
    const parsed = JSON.parse(message);
    if (typeof parsed.detail === "string") {
      return parsed.detail;
    }
    if (Array.isArray(parsed.detail)) {
      return "批改请求格式有误，请重新点击“批改”。如果仍失败，可以重新生成这组题目。";
    }
    return "批改失败，请稍后重试。";
  } catch {
    return message.length > 120 ? `${message.slice(0, 120)}...` : message;
  }
}

function trueFalseValue(value, index) {
  const text = String(value || "").trim().toLowerCase();
  if (text.includes("正确") || text === "true" || text === "对") {
    return "true";
  }
  if (text.includes("错误") || text === "false" || text === "错") {
    return "false";
  }
  return index === 0 ? "true" : "false";
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
