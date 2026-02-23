import streamlit as st
import asyncio
import json
import os
import shutil
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# 1. Page Configuration
st.set_page_config(page_title="Data Research App", layout="wide")

# --- HELPER: Handle Google Credentials ---
def setup_credentials():
    """Service account helper - kept for BQ but silenced if not used."""
    if "gcp_service_account" in st.secrets:
        try:
            creds_path = os.path.join(os.getcwd(), "google_creds.json")
            with open(creds_path, "w") as f:
                json.dump(dict(st.secrets["gcp_service_account"]), f)
            return creds_path
        except Exception:
            pass
    return None

# --- MCP CONFIGURATION ---
# Use '--yes' to bypass interactive prompts that cause SIGTERM on cloud
perplexity_params = StdioServerParameters(
    command="npx",
    args=["--yes", "@perplexity-ai/mcp-server"],
    env={
        "PERPLEXITY_API_KEY": st.secrets.get("PERPLEXITY_API_KEY", ""),
        "HOME": "/tmp",
        "PATH": os.environ.get("PATH", "")
    }
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

# --- HELPER: Extract Text from Content Blocks ---
def extract_text(result):
    """MCP tool results are lists of blocks; we must extract the .text property."""
    if hasattr(result, 'content'):
        parts = [block.text for block in result.content if hasattr(block, 'text')]
        return "\n".join(parts) if parts else "No text content found in blocks."
    return str(result)

async def run_research(prompt):
    try:
        # Start Perplexity Session
        async with stdio_client(perplexity_params) as (r1, w1):
            pplx = ClientSession(r1, w1)
            await pplx.initialize()
            
            # Step 1: Perplexity Search
            st.write("📡 Perplexity: Searching...")
            web_raw = await pplx.call_tool("perplexity_search", {"query": prompt})
            web_text = extract_text(web_raw)
            
            # Step 2: BigQuery Insights (runs only if Perplexity succeeds)
            bq_text = "BigQuery skip/fail"
            try:
                async with stdio_client(bq_params) as (r2, w2):
                    bq = ClientSession(r2, w2)
                    await bq.initialize()
                    st.write("📊 BigQuery: Analyzing...")
                    bq_raw = await bq.call_tool("ask_data_insights", {
                        "query": f"Using this context: {web_text}. Question: {prompt}"
                    })
                    bq_text = extract_text(bq_raw)
            except Exception as bq_e:
                bq_text = f"BigQuery Error: {bq_e}"
                
            return web_text, bq_text
    except Exception as e:
        return f"Perplexity Error: {str(e)}", None

# --- UI ---
st.title("🔍 Data Research App")
query = st.text_input("Enter your query:")

if st.button("Run Research"):
    if query:
        with st.status("Executing Research...") as status:
            # High timeout for npx cold-start
            web_res, bq_res = asyncio.run(asyncio.wait_for(run_research(query), timeout=180.0))
            status.update(label="Workflow Finished", state="complete")
            
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🌐 Web Context")
            st.markdown(web_res if web_res else "Perplexity returned nothing.")
        with col2:
            st.subheader("📊 Data Insights")
            st.markdown(bq_res if bq_res else "BigQuery returned nothing.")