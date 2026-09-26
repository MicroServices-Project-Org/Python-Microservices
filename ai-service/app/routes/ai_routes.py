from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional
from app.services import chatbot, recommendation, suggestion

router = APIRouter()


# ─── Request/Response Schemas ────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    history: Optional[list[dict]] = None

class ChatResponse(BaseModel):
    reply: str

class SuggestRequest(BaseModel):
    query: str

class ProductMatch(BaseModel):
    """Product fields come from the catalog; only the reason comes from the LLM."""
    id: Optional[str] = None
    name: str
    price: Optional[float] = None
    category: Optional[str] = None
    image_url: Optional[str] = None

class Recommendation(ProductMatch):
    reason: str = ""

class RecommendationsResponse(BaseModel):
    recommendations: list[Recommendation]

class SuggestMatch(ProductMatch):
    match_reason: str = ""

class SuggestResponse(BaseModel):
    matches: list[SuggestMatch]
    search_tags: list[str]
    search_category: Optional[str] = None


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def ai_chat(request: ChatRequest):
    """Shopping assistant chatbot powered by LLM."""
    reply = await chatbot.chat(request.message, request.history)
    return ChatResponse(reply=reply)


@router.get("/recommendations", response_model=RecommendationsResponse)
async def ai_recommendations(
    product_name: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
):
    """Get AI-powered product recommendations from real catalog."""
    result = await recommendation.get_recommendations(product_name or "", category or "")
    return RecommendationsResponse(recommendations=result)


@router.post("/suggest", response_model=SuggestResponse)
async def ai_suggest(request: SuggestRequest):
    """Natural language product search — finds matching products from catalog."""
    result = await suggestion.suggest_products(request.query)
    return SuggestResponse(**result)