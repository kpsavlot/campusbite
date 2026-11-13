from sqlalchemy.orm import Query
import math

def paginate(query: Query, page: int, limit: int) -> dict:
    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    pages = math.ceil(total / limit)  if total > 0 else 0

    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages
    }