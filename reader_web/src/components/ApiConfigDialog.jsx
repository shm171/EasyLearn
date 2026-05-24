import { useEffect, useState } from "react";
import { CheckCircle2, KeyRound, Loader2, PlugZap, X } from "lucide-react";
import { getApiConfig, saveApiConfig, testApiConfig } from "../api/client.js";

export default function ApiConfigDialog({ open, onClose }) {
  const [config, setConfig] = useState(null);
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("deepseek-chat");
  const [testMessage, setTestMessage] = useState("请用一句中文回复：API 配置成功。");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    if (!open) {
      return;
    }
    setError("");
    setStatus("");
    setLoading(true);
    getApiConfig()
      .then((data) => {
        setConfig(data);
        setModel(data.deepseek_model || "deepseek-chat");
      })
      .catch((loadError) => setError(loadError.message))
      .finally(() => setLoading(false));
  }, [open]);

  if (!open) {
    return null;
  }

  async function save() {
    setError("");
    setStatus("");
    setLoading(true);
    try {
      const data = await saveApiConfig({
        ai_provider: "deepseek",
        deepseek_model: model,
        deepseek_api_key: apiKey
      });
      setConfig(data);
      setApiKey("");
      setStatus("已保存到本地 .env。");
    } catch (saveError) {
      setError(saveError.message);
    } finally {
      setLoading(false);
    }
  }

  async function test() {
    setError("");
    setStatus("");
    setTesting(true);
    try {
      const data = await testApiConfig({ message: testMessage });
      setStatus(data.answer || "API 调用成功。");
    } catch (testError) {
      setError(testError.message);
    } finally {
      setTesting(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <section className="api-dialog">
        <div className="dialog-head">
          <div>
            <strong>API 配置</strong>
            <span>DeepSeek 聊天模型 · HuggingFace 本地向量</span>
          </div>
          <button type="button" className="icon-button" onClick={onClose} title="关闭">
            <X size={18} />
          </button>
        </div>

        {loading && !config ? (
          <div className="loading-line">
            <Loader2 size={18} className="spin" />
            <span>正在读取本地配置...</span>
          </div>
        ) : null}

        <div className="api-status-row">
          <div>
            <span>当前 Provider</span>
            <strong>{config?.ai_provider || "deepseek"}</strong>
          </div>
          <div>
            <span>API Key</span>
            <strong>{config?.deepseek_api_key_set ? config.deepseek_api_key_preview : "未配置"}</strong>
          </div>
        </div>

        <label>
          DeepSeek API Key
          <input
            value={apiKey}
            onChange={(event) => setApiKey(event.target.value)}
            placeholder={config?.deepseek_api_key_set ? "留空则继续使用当前 Key" : "sk-..."}
            type="password"
            autoComplete="off"
          />
        </label>

        <label>
          模型
          <input value={model} onChange={(event) => setModel(event.target.value)} placeholder="deepseek-chat" />
        </label>

        <label>
          测试消息
          <textarea value={testMessage} onChange={(event) => setTestMessage(event.target.value)} />
        </label>

        {error ? <div className="error-box">{error}</div> : null}
        {status ? (
          <div className="success-box">
            <CheckCircle2 size={18} />
            <span>{status}</span>
          </div>
        ) : null}

        <div className="dialog-actions">
          <button type="button" className="secondary-button" onClick={save} disabled={loading || testing}>
            {loading ? <Loader2 size={17} className="spin" /> : <KeyRound size={17} />}
            <span>保存配置</span>
          </button>
          <button type="button" className="primary-button" onClick={test} disabled={loading || testing}>
            {testing ? <Loader2 size={17} className="spin" /> : <PlugZap size={17} />}
            <span>测试调用</span>
          </button>
        </div>
      </section>
    </div>
  );
}
