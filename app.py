from flask import Flask, request, render_template
import requests
import wikipedia
import re
from urllib.parse import quote
from wikipedia.exceptions import DisambiguationError, PageError
import time

app = Flask(__name__)

API_KEY = "AIzaSyBUmSuF3vuKwO6ItAZir3EFo1zxfvM8ljg"
FACT_CHECK_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"

# Knowledge base of fundamental facts
KNOWLEDGE_BASE = {
    "number of countries in the world": {
        "answer": "There are 195 countries in the world: 193 UN member states and 2 observer states (Vatican City and Palestine).",
        "sources": [
            {
                "source": "United Nations",
                "url": "https://www.un.org/en/member-states/",
                "snippet": "There are currently 193 UN Member States."
            },
            {
                "source": "Worldometer",
                "url": "https://www.worldometers.info/geography/how-many-countries-are-there-in-the-world/",
                "snippet": "There are 195 countries in the world today."
            }
        ]
    },
    "moon composition": {
        "answer": "The Moon is made of rock and minerals, not cheese. It has a solid iron core, a molten outer core, and a mantle and crust made of silicate minerals.",
        "sources": [
            {
                "source": "NASA",
                "url": "https://solarsystem.nasa.gov/moons/earths-moon/in-depth/",
                "snippet": "The Moon is a rocky, solid-surface body with only about one-sixth of Earth's gravity."
            }
        ]
    },
    "earth shape": {
        "answer": "The Earth is an oblate spheroid (slightly flattened at the poles and bulging at the equator), not flat.",
        "sources": [
            {
                "source": "NASA",
                "url": "https://www.nasa.gov/audience/forstudents/k-4/stories/nasa-knows/what-is-earth-k4.html",
                "snippet": "Earth is not a perfect sphere, but rather an oblate spheroid."
            }
        ]
    },
    "country size rankings": {
        "answer": "The largest countries by area are: 1. Russia, 2. Canada, 3. China, 4. United States, 5. Brazil, 6. Australia, 7. India, 8. Argentina, 9. Kazakhstan, 10. Algeria.",
        "sources": [
            {
                "source": "World Atlas",
                "url": "https://www.worldatlas.com/geography/the-largest-countries-in-the-world.html",
                "snippet": "The top 10 largest countries occupy nearly half of the world's land area."
            }
        ]
    },
    "economy size rankings": {
        "answer": "The largest economies by nominal GDP are: 1. United States, 2. China, 3. Japan, 4. Germany, 5. India, 6. United Kingdom, 7. France, 8. Italy, 9. Brazil, 10. Canada.",
        "sources": [
            {
                "source": "IMF",
                "url": "https://www.imf.org/en/Publications/WEO/weo-database/2024/April/weo-report",
                "snippet": "World Economic Outlook Database, April 2024: GDP, current prices (U.S. dollars)."
            },
            {
                "source": "World Bank",
                "url": "https://data.worldbank.org/indicator/NY.GDP.MKTP.CD",
                "snippet": "GDP (current US$) - World Bank national accounts data."
            }
        ]
    }
}

def get_fact_checks(query):
    """Fetch claims from Google Fact Check API."""
    params = {"query": query, "key": API_KEY, "languageCode": "en"}
    try:
        response = requests.get(FACT_CHECK_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException:
        return []

    evidence = []
    for claim in data.get("claims", []):
        claim_text = claim.get("text", "")
        for review in claim.get("claimReview", []):
            rating = review.get("textualRating", "").strip()
            if rating:
                evidence.append({
                    "source": review.get("publisher", {}).get("name", "Unknown Source"),
                    "url": review.get("url", "#"),
                    "snippet": f"{review.get('title','')} — {rating}",
                    "rating": rating.lower(),
                    "claim_text": claim_text
                })
    return evidence

def check_knowledge_base(claim):
    """Check if the claim matches any known facts in our knowledge base."""
    claim_lower = claim.lower()
    
    # Check for country count queries
    if any(phrase in claim_lower for phrase in ["how many countries", "number of countries", "countries in the world"]):
        return KNOWLEDGE_BASE["number of countries in the world"]
    
    # Check for moon composition queries
    if any(phrase in claim_lower for phrase in ["moon made of cheese", "moon is cheese", "moon composition"]):
        return KNOWLEDGE_BASE["moon composition"]
    
    # Check for earth shape queries
    if any(phrase in claim_lower for phrase in ["earth is flat", "flat earth", "earth shape"]):
        return KNOWLEDGE_BASE["earth shape"]
    
    # Check for country size queries
    if any(phrase in claim_lower for phrase in ["largest country", "biggest country", "country size", "largest by area"]):
        return KNOWLEDGE_BASE["country size rankings"]
    
    # Check for economy size queries
    if any(phrase in claim_lower for phrase in ["largest economy", "biggest economy", "economy size", "gdp ranking"]):
        return KNOWLEDGE_BASE["economy size rankings"]
    
    return None

def verify_specific_claim(claim):
    """Verify specific types of claims with precise corrections."""
    claim_lower = claim.lower()
    
    # Economy rankings
    economy_rankings = {
        'united states': 1,
        'china': 2,
        'japan': 3,
        'germany': 4,
        'india': 5,
        'united kingdom': 6,
        'france': 7,
        'italy': 8,
        'brazil': 9,
        'canada': 10
    }
    
    # Area rankings
    area_rankings = {
        'russia': 1,
        'canada': 2,
        'china': 3,
        'united states': 4,
        'brazil': 5,
        'australia': 6,
        'india': 7,
        'argentina': 8,
        'kazakhstan': 9,
        'algeria': 10
    }
    
    # Check for economy ranking claims
    if any(word in claim_lower for word in ['economy', 'gdp', 'economic']):
        for country, rank in economy_rankings.items():
            if country in claim_lower:
                # Extract claimed rank from the statement
                rank_match = re.search(r'(\d+)(?:st|nd|rd|th)', claim_lower)
                if rank_match:
                    claimed_rank = int(rank_match.group(1))
                    if claimed_rank == rank:
                        return True, None, "economy"
                    else:
                        # Generate correction
                        ordinal_suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(rank, 'th')
                        correction = re.sub(
                            r'(\d+)(?:st|nd|rd|th)',
                            f"{rank}{ordinal_suffix}",
                            claim,
                            flags=re.IGNORECASE
                        )
                        return False, correction, "economy"
    
    # Check for area ranking claims
    if any(word in claim_lower for word in ['area', 'size', 'largest', 'biggest']):
        for country, rank in area_rankings.items():
            if country in claim_lower:
                # Extract claimed rank from the statement
                rank_match = re.search(r'(\d+)(?:st|nd|rd|th)', claim_lower)
                if rank_match:
                    claimed_rank = int(rank_match.group(1))
                    if claimed_rank == rank:
                        return True, None, "area"
                    else:
                        # Generate correction
                        ordinal_suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(rank, 'th')
                        correction = re.sub(
                            r'(\d+)(?:st|nd|rd|th)',
                            f"{rank}{ordinal_suffix}",
                            claim,
                            flags=re.IGNORECASE
                        )
                        return False, correction, "area"
    
    return None, None, None

def get_wikipedia_info(claim):
    """Get information from Wikipedia for a claim."""
    try:
        # Search for relevant pages
        search_results = wikipedia.search(claim)
        if not search_results:
            return None, None
        
        # Try to get the most relevant page
        for result in search_results:
            try:
                page = wikipedia.page(result)
                return page, page.summary
            except (DisambiguationError, PageError):
                continue
        return None, None
    except:
        return None, None

def get_wikipedia_sources(claim, max_results=3):
    """Get Wikipedia sources for a claim."""
    sources = []
    try:
        # Search for relevant pages
        search_results = wikipedia.search(claim)
        if search_results:
            for result in search_results[:max_results]:
                try:
                    page = wikipedia.page(result)
                    sources.append({
                        "source": "Wikipedia",
                        "url": page.url,
                        "snippet": f"{page.title}: {page.summary[:200]}...",
                        "rating": "reference"
                    })
                except:
                    continue
    except:
        pass
    return sources

def determine_verdict_and_sources(claim):
    """Determine verdict and return sources with corrected statement."""
    sources = []
    corrected_statement = None
    detailed_verdict = ""
    
    # 1. Check knowledge base first
    knowledge = check_knowledge_base(claim)
    if knowledge:
        verdict = "Verified"
        detailed_verdict = "This information is verified by reliable sources."
        corrected_statement = knowledge["answer"]
        sources.extend(knowledge["sources"])
        
        # Add Wikipedia sources for additional context
        wiki_sources = get_wikipedia_sources(claim)
        sources.extend(wiki_sources)
        
        return verdict, detailed_verdict, corrected_statement, sources
    
    # 2. Check specific claims (economy, area rankings)
    specific_verdict, correction, claim_type = verify_specific_claim(claim)
    if specific_verdict is not None:
        if specific_verdict:
            verdict = "True"
            detailed_verdict = f"The {claim_type} ranking claim is correct."
            corrected_statement = claim
        else:
            verdict = "False"
            detailed_verdict = f"The {claim_type} ranking claim is incorrect."
            corrected_statement = correction
            
            # Add appropriate source based on claim type
            if claim_type == "economy":
                sources.append({
                    "source": "IMF",
                    "url": "https://www.imf.org/en/Publications/WEO/weo-database/2024/April/weo-report",
                    "snippet": "According to IMF data, India is the 5th largest economy by nominal GDP.",
                    "rating": "corrected"
                })
            elif claim_type == "area":
                sources.append({
                    "source": "World Atlas",
                    "url": "https://www.worldatlas.com/geography/the-largest-countries-in-the-world.html",
                    "snippet": "According to World Atlas, India is the 7th largest country by area.",
                    "rating": "corrected"
                })
        
        # Add Wikipedia sources for additional context
        wiki_sources = get_wikipedia_sources(claim)
        sources.extend(wiki_sources)
        
        return verdict, detailed_verdict, corrected_statement, sources
    
    # 3. Use Fact Check API
    evidence = get_fact_checks(claim)
    sources.extend(evidence)
    
    # Analyze fact-check evidence
    true_count = sum(1 for e in evidence if any(keyword in e["rating"] 
                     for keyword in ["true", "correct", "accurate"]))
    false_count = sum(1 for e in evidence if any(keyword in e["rating"] 
                      for keyword in ["false", "incorrect", "inaccurate", "fake"]))
    mixed_count = sum(1 for e in evidence if any(keyword in e["rating"] 
                     for keyword in ["mixture", "partially", "mostly", "somewhat"]))
    
    # Determine verdict based on evidence
    if true_count > 0 and false_count == 0 and mixed_count == 0:
        verdict = "True"
        detailed_verdict = "Verified by multiple fact-check sources."
        corrected_statement = claim
    elif false_count > 0 and true_count == 0 and mixed_count == 0:
        verdict = "False"
        detailed_verdict = "Contradicted by fact-check sources."
    elif mixed_count > 0:
        verdict = "Mixed/Partially True"
        detailed_verdict = "The claim contains both true and false elements."
    elif true_count > 0 and false_count > 0:
        verdict = "Controversial"
        detailed_verdict = "Conflicting evidence from different sources."
    else:
        # 4. Use Wikipedia as fallback
        page, summary = get_wikipedia_info(claim)
        if page and summary:
            # Simple truth detection based on summary content
            summary_lower = summary.lower()
            false_indicators = ["myth", "false", "incorrect", "not true", "debunked", "hoax"]
            true_indicators = ["true", "correct", "accurate", "verified", "confirmed"]
            
            false_count = sum(1 for indicator in false_indicators if indicator in summary_lower)
            true_count = sum(1 for indicator in true_indicators if indicator in summary_lower)
            
            if false_count > true_count:
                verdict = "Likely False"
                detailed_verdict = "Wikipedia suggests this claim may be incorrect."
            elif true_count > false_count:
                verdict = "Likely True"
                detailed_verdict = "Wikipedia suggests this claim may be correct."
                corrected_statement = claim
            else:
                verdict = "Unverified"
                detailed_verdict = "Insufficient evidence to verify this claim."
            
            # Add Wikipedia as source
            sources.append({
                "source": "Wikipedia",
                "url": page.url,
                "snippet": f"{page.title}: {summary[:200]}...",
                "rating": "reference"
            })
        else:
            verdict = "Unverified"
            detailed_verdict = "Insufficient evidence to verify this claim."
    
    # Always add more Wikipedia sources for context
    wiki_sources = get_wikipedia_sources(claim, max_results=5)
    sources.extend(wiki_sources)
    
    return verdict, detailed_verdict, corrected_statement, sources

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        claim = request.form["claim"].strip()
        if not claim:
            return render_template("index.html", error="Please enter a claim to verify")
        
        verdict, detailed_verdict, corrected_statement, sources = determine_verdict_and_sources(claim)
        return render_template(
            "result.html",
            claim=claim,
            verdict=verdict,
            detailed_verdict=detailed_verdict,
            corrected_statement=corrected_statement,
            evidence=sources
        )
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)



