import streamlit as st
import os
from dotenv import load_dotenv
import google.generativeai as genai
from pypdf import PdfReader
from ddgs import DDGS
import concurrent.futures

# Load environment variables
load_dotenv(override=True)

# Page config
st.set_page_config(page_title="Truth-Seeker AI", page_icon="🕵️‍♂️", layout="wide")

# The API Onboarding Screen (Crucial)
api_key = os.getenv("GEMINI_API_KEY")
if not api_key or api_key == "PASTE_YOUR_FREE_KEY_HERE":
    st.warning("Welcome to Truth-Seeker! To bring this AI to life, you need a free API key.\n\n1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey).\n2. Sign in with your Google account and click 'Create API Key' (it is 100% free).\n3. Open the .env file in this project folder and paste your key.\n4. Refresh this page!", icon="⚠️")
    st.stop()

# Configure Gemini API
genai.configure(api_key=api_key)

# Sidebar
with st.sidebar:
    st.title("Settings ⚙️")
    st.markdown("Upload a PDF and enter a search topic to augment the AI's knowledge.")
    uploaded_file = st.file_uploader("Upload PDF Document", type=["pdf"])
    web_topic = st.text_input("Web Search Topic (Optional)", placeholder="Enter topic...", help="If left blank, your chat query will be used as the search topic.")
    st.markdown("---")
    st.caption("MetaRAG: Explainable AI Copilot")

# Chat UI
st.title("Truth-Seeker: Explainable AI Copilot 🤖")
st.markdown("Ask a question! I will search your PDF and the web to find the answer.")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

def extract_pdf_text(uploaded_file):
    if not uploaded_file:
        return "No PDF uploaded."
    try:
        reader = PdfReader(uploaded_file)
        text = ""
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
        # Limit text to avoid exceeding token limits
        return text[:60000] 
    except Exception as e:
        return f"Error reading PDF: {e}"

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

query = st.chat_input("Ask a question about the PDF or the web...")

if query:
    # Append user message
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)
        
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("Searching and Thinking... ⏳")
        
        # Determine the search query
        search_query = web_topic
        if not search_query:
            try:
                # Search engines are bad at long conversational sentences, so we use AI to extract keywords first
                kw_model = genai.GenerativeModel('gemini-3.6-flash')
                search_query = kw_model.generate_content(f"Extract a 2-4 word web search query from this prompt to find the live information the user needs. Ignore parts about a PDF. Only output the keywords. Prompt: {query}").text.strip()
            except Exception:
                search_query = query
        
        # Parallel Execution using ThreadPoolExecutor
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_pdf = executor.submit(extract_pdf_text, uploaded_file)
            future_web = executor.submit(perform_web_search, search_query)
            
            pdf_context = future_pdf.result()
            web_context = future_web.result()
            
        # Construct Prompt
        prompt = f"""
        You are Truth-Seeker, an Explainable AI Copilot.
        Answer the user's question using ONLY the provided context from the uploaded PDF and the Web Search.
        You MUST explicitly cite your sources for every claim you make (e.g., "According to the uploaded PDF..." or "Based on the web search...").
        If the answer cannot be found in the provided context, clearly state that you do not have enough information based on the sources.

        --- CONTEXT FROM PDF ---
        {pdf_context}

        --- CONTEXT FROM WEB SEARCH ---
        {web_context}

        --- USER QUESTION ---
        {query}
        """
        
        try:
            # We use gemini-3.6-flash because it is the latest free-tier model available in 2026
            model = genai.GenerativeModel('gemini-3.6-flash')
            response = model.generate_content(prompt)
            reply = response.text
            
            message_placeholder.markdown(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})
        except Exception as e:
            error_msg = f"An error occurred while generating a response: {e}"
            message_placeholder.markdown(error_msg)
            st.session_state.messages.append({"role": "assistant", "content": error_msg})
