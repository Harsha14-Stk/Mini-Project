# Smart Document Chatbot

This project is a **smart document chatbot** that allows users to ask questions about documents (like PDFs or text files) and get precise answers. It works by:

- **Splitting the document** into smaller chunks.  
- **Creating vector embeddings** for each chunk using a local model (`sentence-transformers`).  
- **Storing the embeddings** in a **FAISS vector database** for fast similarity search.  
- **Using Gemini Flash** to generate human-like answers based on the retrieved relevant chunks.

In short: **upload a document → ask a question → get an intelligent answer.**

## Prerequisites

- Python 3.7 or higher
- MongoDB running on localhost:27017
- Google Gemini API key

## Installation

1. Install the required dependencies:

```bash
pip install -r requirements.txt
```

Or install them manually:

```bash
pip install flask pymongo langchain-google-genai langchain-community faiss-cpu langchain-huggingface PyPDF2 chardet sentence-transformers
```

2. Set up your Google Gemini API key in the [app.py](file:///d:/langchain/app.py) file.

## Usage

1. Make sure MongoDB is running on your system.
2. Run the application:

```bash
python app.py
```

3. Open your browser and go to `http://localhost:5000` to use the chatbot.

## How It Works

The application processes documents by splitting them into chunks, creating vector embeddings, and storing them in a FAISS vector database. When you ask a question, it retrieves the most relevant chunks and uses Gemini Flash to generate a coherent answer.