import os
import concurrent.futures
from fastapi import FastAPI, UploadFile, File, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from database import get_db, ChatMessage
import uuid
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from pypdf import PdfReader
from ddgs import DDGS
import wikipedia

# Load environment variables
load_dotenv(override=True)

app = FastAPI(title="MetaRAG Financial Copilot API")

# Configure CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

mistral_key = os.getenv("MISTRAL_API_KEY")
gemini_key = os.getenv("GEMINI_API_KEY")
groq_key = os.getenv("GROQ_API_KEY")

def extract_and_retrieve_pdf_context(uploaded_file_bytes, query, ai_model):
    if not uploaded_file_bytes:
        return "No PDF uploaded."
    try:
        import io
        pdf_file = io.BytesIO(uploaded_file_bytes)
        reader = PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
        if not text.strip():
            return "PDF contains no readable text."
        
        # 1. Langchain Document Creation & Chunking
        docs = [Document(page_content=text)]
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=300)
        splits = text_splitter.split_documents(docs)
        
        if not splits:
            return "Could not create chunks from PDF."
            
        # 2. Langchain Embeddings & Vectorstore
        if ai_model == "gemini":
            if not gemini_key:
                return "Gemini API key not configured."
            from langchain_google_genai import GoogleGenerativeAIEmbeddings
            embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=gemini_key)
        else:
            if not mistral_key:
                return "Mistral API key not configured."
            from langchain_mistralai import MistralAIEmbeddings
            embeddings = MistralAIEmbeddings(model="mistral-embed", mistral_api_key=mistral_key)
            
        # FAISS handles batching implicitly in LangChain
        vectorstore = FAISS.from_documents(documents=splits, embedding=embeddings)
        
        # 3. Langchain Retriever
        retriever = vectorstore.as_retriever(search_kwargs={"k": 4})
        relevant_docs = retriever.invoke(query)
        
        # 4. Construct Context
        relevant_context = "\n\n---\n\n".join([doc.page_content for doc in relevant_docs])
                
        return relevant_context
    except Exception as e:
        return f"Error processing PDF RAG with LangChain: {e}"

def perform_web_search(query):
    if not query:
        return "No web search query provided."
    try:
        results = DDGS().text(query, max_results=10)
        if not results:
            return "No web search results found."
        search_text = ""
        for r in results:
            search_text += f"Title: {r['title']}\nSnippet: {r['body']}\nLink: {r['href']}\n\n"
        return search_text
    except Exception as e:
        return f"Error performing web search: {e}"

def perform_wikipedia_search(query):
    if not query:
        return "No Wikipedia query provided."
    try:
        search_results = wikipedia.search(query, results=2)
        if not search_results:
            return "No Wikipedia results found."
        
        wiki_text = ""
        for page_title in search_results:
            try:
                page = wikipedia.page(page_title, auto_suggest=False)
                wiki_text += f"Title: {page.title}\nSummary: {page.summary[:1000]}...\nLink: {page.url}\n\n"
            except wikipedia.exceptions.DisambiguationError:
                pass
            except wikipedia.exceptions.PageError:
                pass
        return wiki_text
    except Exception as e:
        return f"Error performing Wikipedia search: {e}"

def get_financial_data(ticker):
    if not ticker or ticker == 'NONE':
        return {"context": "No specific stock ticker identified.", "raw_data": None}
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5d")
        if hist.empty:
            return {"context": f"No financial data found for ticker {ticker}.", "raw_data": None}
        
        info = stock.info
        current_price = info.get('currentPrice', hist['Close'].iloc[-1])
        
        context = f"--- Live Financial Data for {ticker} ---\n"
        context += f"Current Price: ${current_price}\n"
        context += f"52 Week High: ${info.get('fiftyTwoWeekHigh', 'N/A')}\n"
        context += f"52 Week Low: ${info.get('fiftyTwoWeekLow', 'N/A')}\n"
        context += f"Market Cap: ${info.get('marketCap', 'N/A')}\n"
        context += f"Recent 5-day Closing Prices:\n"
        
        raw_data = {
            "ticker": ticker,
            "current_price": current_price,
            "history": []
        }
        
        import math
        for date, row in hist.iterrows():
            price = row['Close']
            if math.isnan(price):
                continue
            context += f"{date.strftime('%Y-%m-%d')}: ${price:.2f}\n"
            raw_data["history"].append({
                "date": date.strftime('%Y-%m-%d'),
                "price": round(price, 2)
            })
        
        return {"context": context, "raw_data": raw_data}
    except Exception as e:
        import traceback
        return {"context": f"Error fetching financial data: {e}", "raw_data": {"error": str(traceback.format_exc())}}

def safe_generate(prompt, ai_model):
    try:
        if ai_model == "gemini":
            if not gemini_key:
                return "Gemini API key not configured."
            from langchain_google_genai import ChatGoogleGenerativeAI
            llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=gemini_key, max_retries=3)
        elif ai_model == "groq":
            if not groq_key:
                return "Groq API key not configured."
            from langchain_groq import ChatGroq
            llm = ChatGroq(model="openai/gpt-oss-20b", groq_api_key=groq_key, max_retries=3)
        else:
            if not mistral_key:
                return "Mistral API key not configured."
            from langchain_mistralai import ChatMistralAI
            llm = ChatMistralAI(model="mistral-small-latest", mistral_api_key=mistral_key, max_retries=3)
            
        response = llm.invoke(prompt)
        return response.content.strip()
    except Exception as e:
        raise e

@app.post("/api/chat")
async def chat_endpoint(
    query: str = Form(...),
    webTopic: str = Form(""),
    baselineMode: bool = Form(False),
    aiModel: str = Form("mistral"),
    activeTab: str = Form("sources"),
    sessionId: str = Form(None),
    file: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    if not sessionId:
        sessionId = str(uuid.uuid4())
        
    finance_raw = None

    if baselineMode:
        prompt = f"""
        You are a Financial Analyst AI.
        Answer the user's question to the best of your ability using only your internal knowledge.
        Do not use any external documents, live web searches, or live market data.
        
        --- USER QUESTION ---
        {query}
        """
    else:
        from pydantic import BaseModel, Field
        class RouteDecision(BaseModel):
            needs_web_search: bool = Field(description="ONLY set to True if the query explicitly requires real-time news, current events, or external facts. Set to False for math (like 1+1), greetings, or general knowledge.")
            needs_wikipedia: bool = Field(description="ONLY set to True if the query asks for deep historical facts, biographies, or encyclopedia entries. Set to False for math, greetings, or simple queries.")
            needs_finance: bool = Field(description="ONLY set to True if the query asks about stock prices, market data, charts, or financial tickers.")
            needs_pdf: bool = Field(description="ONLY set to True if the query explicitly mentions reading an uploaded report, document, or PDF.")

        # Default routing (fallback)
        decision = RouteDecision(needs_web_search=True, needs_wikipedia=True, needs_finance=True, needs_pdf=True)
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            if gemini_key:
                router_llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=gemini_key, temperature=0)
                structured_router = router_llm.with_structured_output(RouteDecision)
                decision = structured_router.invoke(f"Analyze this query and decide which tools to use. Query: {query}")
        except Exception as e:
            print(f"Router failed, falling back to all tools. Error: {e}")

        search_query = webTopic
        ticker = 'NONE'
        pdf_context, web_context, wiki_context, finance_context = "", "", "", ""
        file_bytes = await file.read() if file else None
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {}
            
            if decision.needs_pdf and file_bytes:
                futures['pdf'] = executor.submit(extract_and_retrieve_pdf_context, file_bytes, query, aiModel)
                
            if decision.needs_web_search or decision.needs_wikipedia:
                if not search_query:
                    try:
                        search_query = safe_generate(f"Extract a 2-4 word web search query from this prompt. Ignore parts about a PDF. Only output the keywords. Prompt: {query}", aiModel)
                    except Exception:
                        search_query = query
                
                if decision.needs_web_search:
                    futures['web'] = executor.submit(perform_web_search, search_query)
                if decision.needs_wikipedia:
                    futures['wiki'] = executor.submit(perform_wikipedia_search, search_query)
                    
            if decision.needs_finance:
                try:
                    ticker_raw = safe_generate(f"Extract ONLY the stock ticker symbol (e.g. AAPL). Output nothing else. If none, output NONE. Query: {query}", aiModel).upper().strip()
                    ticker_raw = ticker_raw.replace('.', '').replace(',', '').replace('`', '')
                    ticker = ticker_raw.split()[-1] if ' ' in ticker_raw else ticker_raw
                except Exception:
                    ticker = 'NONE'
                futures['finance'] = executor.submit(get_financial_data, ticker)
                
            if 'pdf' in futures: pdf_context = futures['pdf'].result()
            if 'web' in futures: web_context = futures['web'].result()
            if 'wiki' in futures: wiki_context = futures['wiki'].result()
            if 'finance' in futures: 
                finance_result = futures['finance'].result()
                finance_context = finance_result["context"]
                finance_raw = finance_result["raw_data"]
            
        prompt = f"""
    You are an expert Financial Analyst Copilot.
    Answer the user's question using the provided context from the uploaded Financial Report (PDF), Live Financial Market Data, the Live Web Search, and Wikipedia.
    IMPORTANT RULES:
    1. If a context section says "No PDF uploaded", "No specific stock ticker identified", or "Error", IGNORE IT completely. Do NOT mention that you cannot access it, do NOT apologize, and do NOT say there was an error.
    2. If the provided context is empty or insufficient, you MUST answer the user's question using your own internal knowledge. Do NOT refuse to answer.
    3. Explicitly cite sources if you use them (e.g., "According to Yahoo Finance...", "Based on live web search...").
    4. CRITICAL RULES FOR CHARTS/VISUALS:
       - Do NOT output external markdown image links.
       - Do NOT draw ASCII text graphs/charts in your response.
       - NEVER tell the user to switch tabs, click anything, or look at a sidebar. The UI handles visualizations automatically. Just provide the textual financial analysis.

    5. CONTEXT AWARENESS & MEMORY:
       - The user is currently on the '{activeTab}' tab.
       - If they are on the 'visuals' tab, you MUST provide an ultra-concise (1-2 sentences) summary of the price/trend. Let the graph do the talking. Do not write long paragraphs.
       - CRITICAL: You are a stateful AI. The section --- RECENT CHAT HISTORY --- contains your actual memory. If the user asks what they just said or what the last conversation was, YOU MUST READ the RECENT CHAT HISTORY section and summarize it for them. NEVER say "I don't have a record of your previous chat."

    --- CONTEXT FROM UPLOADED REPORT (PDF) ---
    {pdf_context}

    --- CONTEXT FROM LIVE FINANCIAL MARKET DATA ---
    {finance_context}

    --- CONTEXT FROM LIVE WEB SEARCH (DuckDuckGo) ---
    {web_context}

    --- CONTEXT FROM ENCYCLOPEDIA (Wikipedia) ---
    {wiki_context}
    """
    
    # Fetch chat memory from MySQL database
    chat_history_str = ""
    try:
        past_msgs = db.query(ChatMessage).filter(ChatMessage.session_id == sessionId).order_by(ChatMessage.created_at.desc()).limit(5).all()
        past_msgs.reverse() # chronological order
        for msg in past_msgs:
            role_label = "User" if msg.role == "user" else "Assistant"
            chat_history_str += f"{role_label}: {msg.content}\n"
    except Exception as e:
        chat_history_str = "Error fetching chat history."

    if chat_history_str:
        prompt += f"\n\n    --- RECENT CHAT HISTORY ---\n    {chat_history_str}"

    prompt += f"\n\n    --- USER QUESTION ---\n    {query}\n    "
    
    try:
        reply = safe_generate(prompt, aiModel)
        
        # Save memory to database
        try:
            db.add(ChatMessage(session_id=sessionId, role="user", content=query))
            db.add(ChatMessage(session_id=sessionId, role="assistant", content=reply))
            db.commit()
        except Exception as e:
            print(f"Error saving to db: {e}")
            db.rollback()
            
        return {"reply": reply, "financialData": finance_raw, "sessionId": sessionId}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/health")
def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
