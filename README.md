# Truth-Seeker: MetaRAG Explainable AI Copilot

Truth-Seeker is a Python-based MetaRAG (Metasearch + Retrieval-Augmented Generation) application with a Streamlit UI, functioning as an "Explainable AI Copilot." It allows users to ask questions and receive answers based on two concurrent sources of information: an uploaded PDF document and live web search results.

## What is MetaRAG?

MetaRAG stands for Metasearch + Retrieval-Augmented Generation. 
- **Retrieval-Augmented Generation (RAG)** is a technique where an AI model (like Google's Gemini) is provided with external, relevant information (like a PDF document) to help it answer questions more accurately and with less hallucination.
- **Metasearch** expands this by querying multiple search engines or databases concurrently. 

In this application, we combine a standard document RAG (using the uploaded PDF) with a live web metasearch (using DuckDuckGo) to provide the AI with a rich, up-to-date context to answer your questions. The AI is specifically instructed to use **only** this context and to **explicitly cite its sources**, making it an "Explainable" AI Copilot.

## How the Code Works

1. **Environment Setup**: The application uses `dotenv` to load API keys securely from a `.env` file.
2. **Streamlit UI**: `app.py` builds a responsive, dark-mode friendly chat interface. It includes a sidebar for document uploads and web search topics.
3. **API Onboarding Screen**: At startup, the code checks if the `GEMINI_API_KEY` is present and valid. If not, it halts execution and gracefully guides the user to obtain one.
4. **Parallel Processing**: When a user asks a question, the backend uses `concurrent.futures.ThreadPoolExecutor` to simultaneously extract text from the PDF and fetch web search results using `duckduckgo-search`.
5. **AI Integration**: The retrieved text from both sources is injected into a strict prompt. This prompt is sent to the Google Gemini API (`google-generativeai`), which generates a response strictly based on the provided context with citations.

## How to Get the API Key (100% Free)

1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey).
2. Sign in with your Google account.
3. Click **Create API Key**.
4. Open the `.env` file in this project folder.
5. Paste your key over the placeholder text (`PASTE_YOUR_FREE_KEY_HERE`).

## How to Run the Application Locally

Follow these steps to run Truth-Seeker for your presentation:

1. **Open your terminal** and navigate to this project folder (`metarag_copilot`).
2. **Activate the virtual environment**:
   - On Windows: `.\venv\Scripts\Activate.ps1`
   - On macOS/Linux: `source venv/bin/activate`
3. **Install dependencies** (if not already installed):
   - `pip install streamlit pypdf duckduckgo-search google-generativeai python-dotenv`
4. **Run the Streamlit application**:
   - `streamlit run app.py`
5. The application will automatically open in your default web browser (typically at `http://localhost:8501`).

Enjoy your presentation!
