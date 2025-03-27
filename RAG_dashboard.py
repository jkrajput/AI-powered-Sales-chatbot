import pandas as pd
from dotenv import load_dotenv
import os
import google.generativeai as genai
import re
import streamlit as st

# Step 1: Load the Excel Data
def load_data(file_path='100 data.xlsx'):
    try:
        df = pd.read_excel(file_path, sheet_name= 'Sheet1')
        st.write(f"Loaded Excel file with {len(df)} rows")
        return df
    except FileNotFoundError:
        st.error(f"Error: '{file_path}' not found.")
        return None
    except Exception as e:
        st.error(f"Error reading the file: {e}")
        return None

# Step 2: Configure Gemini
def setup_gemini():
    load_dotenv()
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    if not GOOGLE_API_KEY:
        st.error("Error: GOOGLE_API_KEY not found in environment variables.")
        return None, None

    genai.configure(api_key=GOOGLE_API_KEY)
    
    code_instruction = """You are an expert data analyst with strong pandas skills. 
    Given a user query and a sample of a pandas DataFrame named 'df', generate the exact pandas code to compute the answer.
    Always use 'df' as the DataFrame name (never 'pandasdf' or other names). 
    Use 'Sales' as the column for sales data unless specified otherwise. 
    If the query asks for a graph or table, return a pandas expression that evaluates to a DataFrame with appropriate columns (e.g., df.groupby('column')['value'].sum().reset_index()), 
    without calling .plot() or other visualization methods. 
    Otherwise, return a single-line pandas expression that evaluates to the final result (e.g., a number, string, Series, or DataFrame), 
    without using print(), semicolons for multiple statements, or extra text."""
    
    response_instruction = """You are an expert data analyst. 
    Given a user query and a computed result (which may be a number, string, or table as text), 
    format the result into a concise, natural language answer. 
    If the result is a table or for a graph, provide a brief summary highlighting key insights."""
    
    code_model = genai.GenerativeModel("models/gemini-2.0-flash", system_instruction=code_instruction)
    response_model = genai.GenerativeModel("models/gemini-2.0-flash", system_instruction=response_instruction)
    
    return code_model.start_chat(), response_model.start_chat()

# Step 3: Define the Query Processing Function
def process_query(df, code_chat, response_chat, question, sample_size=5):
    if not question:
        return "Please enter a question."
    
    # Get a small sample of the DataFrame
    sample_df = df.head(sample_size).to_string()
    
    # Step 1: Ask LLM to generate pandas code
    code_prompt = f"Query: {question}\nDataFrame sample (df):\n{sample_df}"
    code_response = code_chat.send_message(code_prompt)
    raw_code = code_response.text.strip()
    
    # Clean the code
    pandas_code = re.sub(r'```python|```|\n', '', raw_code).strip()
    pandas_code = pandas_code.replace('pandasdf', 'df')  # Fallback fix
    st.write(f"**Generated pandas code:** `{pandas_code}`")
    
    # Step 2: Execute the pandas code
    try:
        result = eval(pandas_code, {'df': df, 'pd': pd})
        
        # Check if the result is a DataFrame and handle accordingly
        if isinstance(result, pd.DataFrame):
            # Detect graph request
            if 'graph' in question.lower() or 'plot' in question.lower():
                st.write("**Computed result (data for graph):**")
                st.dataframe(result)  # Show the data
                # Plot the graph (assuming two columns: x-axis and y-axis)
                if len(result.columns) >= 2:
                    result = result.set_index(result.columns[0])  # Set first column as index
                    st.line_chart(result)  # Default to line chart
                else:
                    st.bar_chart(result)  # Use bar chart for single-column DataFrame
            else:
                # Display as table
                st.write("**Computed result (table):**")
                st.dataframe(result)
            result_str = result.to_string()  # Convert to string for LLM
        else:
            st.write(f"**Computed result:** {result}")
            result_str = str(result)
    except Exception as e:
        st.error(f"Error executing pandas code: {e}")
        result_str = f"Error: Could not compute the answer due to {e}"
        return result_str

    # Step 3: Ask LLM to format the result
    response_prompt = f"Query: {question}\nComputed result: {result_str}"
    response = response_chat.send_message(response_prompt)
    return response.text

# Main Streamlit App
def main():
    st.title("Sales Chatbot Dashboard")
    st.write("Ask questions about your sales data and get answers powered by AI!")

    # Load data
    df = load_data('100 data.xlsx')
    if df is None:
        return

    # Setup Gemini
    code_chat, response_chat = setup_gemini()
    if code_chat is None or response_chat is None:
        return

    # User input
    user_question = st.text_input("Enter your question here (e.g., 'Draw a graph for day-wise sales')")
    
    # Process query when user submits
    if st.button("Get Answer"):
        with st.spinner("Processing your question..."):
            answer = process_query(df, code_chat, response_chat, user_question)
            st.write("**Answer:**", answer)

if __name__ == "__main__":
    main()