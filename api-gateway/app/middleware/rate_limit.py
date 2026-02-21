from slowapi import Limiter
from slowapi.util import get_remote_address
from app.config import settings

# Rate limiter — uses client IP as the key
limiter = Limiter(key_func=get_remote_address)