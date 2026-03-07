import asyncio
from typing import List, Dict, Any
from edgar import set_identity, Company
from app.llm import get_llm
from langchain_core.messages import HumanMessage
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Set identity for SEC Edgar wrapper
set_identity("Agentic Analyzer info@hardikkhandelwal.com")

def get_recent_filings_metadata(ticker: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Retrieves a list of recent filings for the UI."""
    try:
        company = Company(ticker)
        if not company:
            return []
            
        # Get all recent filings
        filings = company.get_filings()
        if filings.empty:
            return []
            
        # Extract metadata
        result = []
        # Usually filings is a Filings object which can be iterated
        for i, f in enumerate(filings):
            if i >= limit:
                break
            result.append({
                "form": f.form,
                "date": str(f.filing_date),
                "acc_num": f.accession_no,
                "document": f.document.url if hasattr(f, 'document') and f.document else ""
            })
            
        return result
    except Exception as e:
        print(f"[Error] get_recent_filings_metadata: {e}")
        return []

def _extract_10k_section(ticker: str, section_name: str) -> str:
    """Helper to extract a specific section from the latest 10-K (e.g., 'Item 7' or 'Item 1A')."""
    try:
        company = Company(ticker)
        if not company:
            return ""
            
        filings = company.get_filings(form="10-K")
        if filings.empty:
            return ""
            
        tenk_filing = filings[0]
        tenk_obj = tenk_filing.obj()
        
        if not tenk_obj:
            return ""
            
        try:
            section_text = tenk_obj[section_name]
            return section_text
        except Exception:
            return ""
    except Exception as e:
        print(f"[Error] _extract_10k_section({section_name}): {e}")
        return ""

def _map_reduce_summarize(text: str, map_prompt_template: str, reduce_prompt_template: str, max_chunk_size: int = 15000) -> str:
    """Helper to split large text into chunks, summarize each chunk (Map), and then summarize the summaries (Reduce)."""
    # 1. Split the text into chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=max_chunk_size,
        chunk_overlap=500,
        length_function=len,
    )
    chunks = text_splitter.split_text(text)
    
    llm = get_llm(temperature=0.2)
    
    # 2. Map: Summarize each chunk
    chunk_summaries = []
    for i, chunk in enumerate(chunks):
        if i >= 4: # Hard limit: max 4 chunks (~60k chars) to avoid excessive API calls
            break
            
        map_prompt = map_prompt_template.format(chunk=chunk)
        try:
            response = llm.invoke([HumanMessage(content=map_prompt)])
            chunk_summaries.append(response.content)
        except Exception as e:
            print(f"[Map Error] Chunk {i}: {e}")
            
    if not chunk_summaries:
        return "Failed to generate initial summaries."
        
    # If we only have 1 chunk, no need to reduce
    if len(chunk_summaries) == 1:
        return chunk_summaries[0]
        
    # 3. Reduce: Summarize the summaries
    combined_summaries = "\n\n---\n\n".join(chunk_summaries)
    
    # Check if the combined summaries are too large (edge case)
    if len(combined_summaries) > max_chunk_size:
        combined_summaries = combined_summaries[:max_chunk_size]
        
    reduce_prompt = reduce_prompt_template.format(combined_summaries=combined_summaries)
    
    try:
        response = llm.invoke([HumanMessage(content=reduce_prompt)])
        return response.content
    except Exception as e:
        print(f"[Reduce Error]: {e}")
        return "Failed to generate final synthesis from summaries."

def generate_mda_summary(ticker: str) -> str:
    """Extracts 'Item 7' (MD&A) from the latest 10-K and summarizes it using a Map-Reduce approach."""
    mda_text = _extract_10k_section(ticker, "Item 7")
    if not mda_text:
        return "Failed to extract Management's Discussion and Analysis (MD&A) from the latest 10-K filing."
        
    map_prompt = (
        f"You are a financial analyst reviewing a section of the Management's Discussion & Analysis (MD&A) for {ticker}.\n"
        f"Extract the key financial narrative, operational highlights, and forward-looking guidance from this specific excerpt.\n\n"
        f"Excerpt:\n{{chunk}}\n\n"
        f"Summary:"
    )
    
    reduce_prompt = (
        f"You are an expert financial analyst. Read the following summaries of different sections of the latest MD&A for {ticker}.\n\n"
        f"Synthesize them into a single, comprehensive markdown report focused on:\n"
        f"1. Core business performance and operational highlights.\n"
        f"2. Forward-looking guidance or management outlook.\n"
        f"3. Key financial narrative (revenue drivers, margin shifts).\n\n"
        f"Keep the overarching report structured with headings and bullet points.\n\n"
        f"Combined Section Summaries:\n{{combined_summaries}}\n\n"
        f"Final MD&A Synthesis:"
    )
    
    # Use max_chunk_size=12000 to stay safely under Groq's 6k TPM limit per chunk
    return _map_reduce_summarize(mda_text, map_prompt, reduce_prompt, max_chunk_size=12000)

def generate_risk_summary(ticker: str) -> str:
    """Extracts 'Item 1A' (Risk Factors) from the latest 10-K and summarizes it using a Map-Reduce approach."""
    risk_text = _extract_10k_section(ticker, "Item 1A")
    if not risk_text:
        return "Failed to extract Risk Factors from the latest 10-K filing."
        
    map_prompt = (
        f"You are a risk analyst reviewing a section of the Risk Factors for {ticker}.\n"
        f"Identify any critical, newly emerging, or structural risks mentioned in this excerpt. Ignore generic boilerplate.\n\n"
        f"Excerpt:\n{{chunk}}\n\n"
        f"Key Risks Found:"
    )
    
    reduce_prompt = (
        f"You are an expert risk analyst. Read the following summaries of different risk sections for {ticker}.\n\n"
        f"Identify the absolute top 3-5 most critical risk factors facing the company.\n"
        f"Provide a concise, synthesized markdown summary highlighting only these major structural or macroeconomic risks.\n\n"
        f"Combined Risk Summaries:\n{{combined_summaries}}\n\n"
        f"Final Top Risk Factors:"
    )
    
    return _map_reduce_summarize(risk_text, map_prompt, reduce_prompt, max_chunk_size=12000)
