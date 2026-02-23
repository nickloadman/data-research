import streamlit as st
import asyncio
import json
import os
import shutil
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

st.set_page_config(page_title="Data Research App", layout="wide")

# --- CREDENTIALS ---
def setup_credentials():
    if "gcp_service_account" in st.secrets:
        creds_path = os.path.join(os.getcwd(), "google_creds.json")
        with open(creds_path, "w") as f:
            json.dump(dict(st.secrets["gcp_service_account"]), f)
        return creds_path
    return None

# --- MCP CONFIG ---
perplexity_params = StdioServerParameters(
    command="npx",
    args=["-y", "@perplexity-ai/mcp-server"],
    env={"PERPLEXITY_API_KEY": st.secrets.get("PERPLEXITY_API_KEY", ""), "HOME": "/tmp"}
)

toolbox_path = shutil.which("toolbox") or "toolbox"
bq_params = StdioServerParameters(
    command=toolbox_path,
    args=["--prebuilt", "bigquery", "--stdio"],
    env={
        "GOOGLE_APPLICATION_CREDENTIALS": setup_credentials() or "",
        "BIGQUERY_PROJECT": "apac-sandbox"
    }
)

# --- HELPER TO EXTRACT TEXT ---
def parse_mcp_result(result):
    """MCP tools return a list of content blocks. This extracts the text."""
    if not result or not hasattr(result, 'content'):
        return "No data returned."
    
    # Join all text blocks found in the result
    texts = [block.text for block in result.content if hasattr(block, 'text')]
    return "\n".join(texts) if texts else "Empty content blocks."

async def run_workflow(prompt):
    try:
        async with stdio_client(perplexity_params) as (r1, w1), \
                   stdio_client(bq_params) as (r2, w2):
            
            pplx = ClientSession(r1, w1)
            bq = ClientSession(r2, w2)
            await pplx.initialize()
            await bq.initialize()

            # Step 1: Perplexity Search
            web_raw = await pplx.call_tool("perplexity_search", {"query": prompt})
            web_text = parse_mcp_result(web_raw)
            
            # Step 2: BigQuery Insights
            # Using the extracted text from Perplexity as context
            bq_raw = await bq.call_tool("ask_data_insights", {
                "query": f"Using this web context: {web_text}. Question: {prompt}"
            })
            bq_text = parse_mcp_result(bq_raw)
            
            return web_text, bq_text
    except Exception as e:
        return f"Error: {e}", None

# --- UI ---
st.title("🔍 Data Research App")
query = st.text_input("What is your research question?")

if st.button("Run Research"):
    if query:
        with st.status("Executing Research Workflow...") as status:
            res_web, res_bq = asyncio.run(run_workflow(query))
            status.update(label="Workflow Complete!", state="complete")
            
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🌐 Web Context (Perplexity)")
            st.markdown(res_web)
            
        with col2:
            st.subheader("📊 Data Insights (BigQuery)")
            st.markdown(res_bq)