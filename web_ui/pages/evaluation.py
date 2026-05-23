from __future__ import annotations

"""Quiz answering and evaluation page."""

import streamlit as st

from web_ui.ui_utils import DEBUG_DIR, render_list_or_json, safe_show_exception, save_json_utf8, show_json_download_button, to_jsonable, uploaded_json


def _questions_from_quiz(quiz: dict) -> list[dict]:
    questions = quiz.get("questions", [])
    return questions if isinstance(questions, list) else []


def _display_report(report: dict) -> None:
    st.subheader("评估报告")
    st.metric("total_score", report.get("total_score", 0))

    question_results = report.get("question_results", [])
    if question_results:
        st.subheader("每题结果")
        for item in question_results:
            title = f"{item.get('question_id', '')} · {'正确' if item.get('is_correct') else '需复习'} · {item.get('score', 0)}"
            with st.expander(title, expanded=True):
                st.write(f"用户答案：{item.get('user_answer', '')}")
                st.write(f"正确答案：{item.get('correct_answer', '')}")
                st.write(f"反馈：{item.get('feedback', '')}")
                st.write(f"解释：{item.get('explanation', '')}")
                st.write("知识点")
                render_list_or_json(item.get("knowledge_points", []))
                st.write("推荐复习 chunks")
                render_list_or_json(item.get("recommended_review_chunks", []))
    else:
        st.json(report, expanded=True)

    st.subheader("错误知识点")
    render_list_or_json(report.get("wrong_knowledge_points", []))
    st.subheader("薄弱点总结")
    st.write(report.get("weakness_summary", ""))
    st.subheader("下一步学习计划")
    render_list_or_json(report.get("next_study_plan", []))
    st.subheader("推荐复习 chunks")
    render_list_or_json(report.get("recommended_review_chunks", []))


def render() -> None:
    """Render the quiz answering and evaluation page."""

    st.title("答题与批改")

    quiz = st.session_state.get("last_quiz")
    if quiz is None:
        uploaded_file = st.file_uploader("上传 quiz.json", type=["json"])
        if uploaded_file is not None:
            try:
                quiz = uploaded_json(uploaded_file)
                st.session_state.last_quiz = quiz
                st.success("quiz.json 已加载。")
            except Exception as exc:
                safe_show_exception(exc)
                return
    else:
        st.success("已读取当前 session 中最近生成的 quiz。")

    if quiz is None:
        st.info("请先到“生成题目”页面生成题目，或上传 quiz.json。")
        return

    quiz_data = to_jsonable(quiz)
    questions = _questions_from_quiz(quiz_data)
    if not questions:
        st.warning("quiz 中没有可批改的题目。")
        st.json(quiz_data, expanded=True)
        return

    st.subheader("填写答案")
    user_answers: list[dict[str, str]] = []
    for index, question in enumerate(questions, start=1):
        question_id = question.get("question_id") or f"q{index}"
        question_type = question.get("question_type", "")
        with st.container():
            st.markdown(f"### 题号 {index}: {question_id}")
            st.write(f"题型：{question_type}")
            st.write(question.get("stem", ""))
            if question.get("code_snippet"):
                st.code(question["code_snippet"], language=quiz_data.get("programming_language", "python"))
            if question.get("options"):
                render_list_or_json(question["options"])

            key = f"answer_{question_id}"
            if question_type == "true_false":
                answer = st.selectbox("答案", ["true", "false"], key=key)
            else:
                answer = st.text_area("答案", key=key, height=120)
            user_answers.append({"question_id": str(question_id), "answer": str(answer)})

    if st.button("提交批改", type="primary"):
        try:
            with st.spinner("正在批改答案..."):
                report = st.session_state.service.evaluate_answers(quiz=quiz_data, user_answers=user_answers)
            data = to_jsonable(report)
            st.session_state.last_report = report
            save_json_utf8(DEBUG_DIR / "report_web.json", data)
            st.success("批改完成。")
        except Exception as exc:  # pragma: no cover - depends on local model env
            st.error("批改失败：模型返回格式不符合要求，或评估模块返回空内容。")
            with st.expander("错误详情"):
                st.exception(exc)

    if st.session_state.get("last_report") is not None:
        report_data = to_jsonable(st.session_state.last_report)
        _display_report(report_data)
        show_json_download_button("下载 report_web.json", report_data, "report_web.json")


if __name__ == "__main__":
    from web_ui.state import init_session_state

    init_session_state()
    render()
