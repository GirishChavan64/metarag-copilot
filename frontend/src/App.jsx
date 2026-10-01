import React, { useState, useRef, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Menu, Activity, Settings, ChevronLeft, ChevronRight } from 'lucide-react';
import './index.css';

function App() {
  const [messages, setMessages] = useState([]);
  const [inputQuery, setInputQuery] = useState('');
  const [webTopic, setWebTopic] = useState('');
  const [file, setFile] = useState(null);
  const [baselineMode, setBaselineMode] = useState(false);
  const [aiModel, setAiModel] = useState('mistral');
  const [isLoading, setIsLoading] = useState(false);

  // Sidebar states
  const [isSidebarOpen, setIsSidebarOpen] = useState(window.innerWidth > 768);
  const [sidebarTab, setSidebarTab] = useState('sources'); // 'sources' or 'visuals'

  // Data states
  const [financialData, setFinancialData] = useState(null);
  
  // Chat Memory
  const [sessionId, setSessionId] = useState(() => localStorage.getItem('chatSessionId') || '');

  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!inputQuery.trim()) return;

    const userMsg = inputQuery;
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setInputQuery('');
    setIsLoading(true);

    const formData = new FormData();
    formData.append('query', userMsg);
    formData.append('webTopic', webTopic);
    formData.append('baselineMode', baselineMode);
    formData.append('aiModel', aiModel);
    formData.append('activeTab', sidebarTab);
    if (sessionId) {
      formData.append('sessionId', sessionId);
    }
    if (file) {
      formData.append('file', file);
    }

    try {
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();

      if (data.error) {
        setMessages(prev => [...prev, { role: 'assistant', content: `Error: ${data.error}` }]);
      } else {
        if (data.sessionId && !sessionId) {
          setSessionId(data.sessionId);
          localStorage.setItem('chatSessionId', data.sessionId);
        }
        setMessages(prev => [...prev, { role: 'assistant', content: data.reply }]);
        if (data.financialData && data.financialData.history && data.financialData.history.length > 0) {
          setFinancialData(data.financialData);
          setSidebarTab('visuals');
          setIsSidebarOpen(true);
        }
      }
    } catch (error) {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Failed to connect to the backend server. Make sure FastAPI is running.' }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="app-container">
      {/* Unified Sidebar */}
      <aside className={`sidebar ${isSidebarOpen ? 'open' : 'closed'}`}>
        <div className="logo-section">
          <h1>Financial Copilot 📈</h1>
          <p>MetaRAG: Explainable AI</p>
        </div>

        <div className="sidebar-tabs-header">
          <button
            className={`sidebar-tab-btn ${sidebarTab === 'sources' ? 'active' : ''}`}
            onClick={() => setSidebarTab('sources')}
          >
            <Settings size={16} /> Inputs
          </button>
          <button
            className={`sidebar-tab-btn ${sidebarTab === 'visuals' ? 'active' : ''}`}
            onClick={() => setSidebarTab('visuals')}
          >
            <Activity size={16} /> Visuals
          </button>
        </div>

        <div className="sidebar-content-scroll">
          {sidebarTab === 'sources' && (
            <div className="sidebar-panel">
              <div className="settings-group">
                <h3>Knowledge Sources</h3>
                <label>
                  Company Report (PDF)
                  <input
                    type="file"
                    accept=".pdf"
                    onChange={(e) => setFile(e.target.files[0])}
                  />
                </label>

                <label>
                  Web Search Topic
                  <input
                    type="text"
                    placeholder="e.g., Tesla stock news..."
                    value={webTopic}
                    onChange={(e) => setWebTopic(e.target.value)}
                  />
                </label>
              </div>



              <div className="settings-group">
                <h3>AI Mode Selection</h3>
                <div className="mode-selector">
                  <button
                    type="button"
                    className={`mode-btn ${baselineMode ? 'active' : ''}`}
                    onClick={() => setBaselineMode(true)}
                  >
                    Normal LLM
                  </button>
                  <button
                    type="button"
                    className={`mode-btn ${!baselineMode ? 'active' : ''}`}
                    onClick={() => setBaselineMode(false)}
                  >
                    MetaRAG
                  </button>
                </div>
                <p style={{ fontSize: '0.8rem', color: '#64748b', margin: '0.5rem 0' }}>
                  {baselineMode
                    ? "Standard AI. No live data, no PDFs, no visuals."
                    : "Advanced AI. Live market data and PDF analysis."}
                </p>
              </div>
            </div>
          )}

          {sidebarTab === 'visuals' && (
            <div className="sidebar-panel">
              <h4>Live Financial Data</h4>
              {financialData ? (
                <div className="finance-dashboard">
                  <div className="metric-card">
                    <span className="metric-label">Ticker</span>
                    <span className="metric-value">{financialData.ticker}</span>
                  </div>
                  <div className="metric-card">
                    <span className="metric-label">Current Price</span>
                    <span className="metric-value">${financialData.current_price}</span>
                  </div>
                  <h5 style={{ marginTop: '1rem', marginBottom: '0.5rem', color: '#64748b' }}>5-Day Price Trend</h5>
                  <div className="chart-container">
                    <ResponsiveContainer width="100%" height={200}>
                      <LineChart data={financialData.history} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                        <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                        <YAxis domain={['auto', 'auto']} tick={{ fontSize: 10 }} />
                        <Tooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
                        <Line type="monotone" dataKey="price" stroke="#3b82f6" strokeWidth={3} dot={{ r: 4, fill: '#3b82f6' }} activeDot={{ r: 6 }} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              ) : (
                <p className="placeholder-text">Ask a question about a publicly traded company to see live stock data visualizations.</p>
              )}
            </div>
          )}
        </div>
      </aside>

      {/* Main Chat Area */}
      <main className="chat-container">
        <div className="chat-header">
          <button type="button" className="menu-toggle" onClick={() => setIsSidebarOpen(!isSidebarOpen)} title="Toggle Sidebar">
            {isSidebarOpen ? <ChevronLeft size={20} /> : <ChevronRight size={20} />}
          </button>
        </div>
        <div className="chat-messages">
          {messages.length === 0 && (
            <div className="message assistant" style={{ alignSelf: 'center', marginTop: 'auto', marginBottom: 'auto', textAlign: 'center' }}>
              <h2 style={{ color: '#60a5fa' }}>Welcome to your Financial Copilot.</h2>
              <p>Upload a report on the left and ask a question to begin your MetaRAG analysis.</p>
            </div>
          )}

          {messages.map((msg, index) => (
            <div key={index} className={`message ${msg.role}`}>
              <div className="message-content">{msg.content}</div>
            </div>
          ))}

          {isLoading && (
            <div className="typing-indicator">
              {baselineMode ? "Thinking (Baseline Mode)... ⏳" : "Agent is thinking... ⏳"}
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="input-area">
          <form className="input-form" onSubmit={handleSubmit}>
            <select
              className="inline-model-select"
              value={aiModel}
              onChange={(e) => setAiModel(e.target.value)}
              title="Select AI Model"
            >
              <option value="mistral">Mistral Small</option>
              <option value="gemini">Gemini</option>
              <option value="groq">Groq (Llama 3)</option>
            </select>
            <input
              type="text"
              placeholder="Ask a question about the report or the market..."
              value={inputQuery}
              onChange={(e) => setInputQuery(e.target.value)}
              disabled={isLoading}
            />
            <button type="submit" className="submit-btn" disabled={isLoading || !inputQuery.trim()}>
              Send
            </button>
          </form>
        </div>
      </main>
    </div>
  );
}

export default App;
