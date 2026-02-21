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

class SuggestResponse(BaseModel):
    result: str


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def ai_chat(request: ChatRequest):
    """Shopping assistant chatbot powered by LLM."""
    reply = await chatbot.chat(request.message, request.history)
    return ChatResponse(reply=reply)


@router.get("/recommendations")
async def ai_recommendations(
    product_name: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
):
    """Get AI-powered product recommendations from real catalog."""
    result = await recommendation.get_recommendations(product_name, category)
    return {"recommendations": result}


@router.post("/suggest", response_model=SuggestResponse)
async def ai_suggest(request: SuggestRequest):
    """Natural language product search — finds matching products from catalog."""
    result = await suggestion.suggest_products(request.query)
    return SuggestResponse(result=result)