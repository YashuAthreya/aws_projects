# app/user_service.py

import re


def build_user_filters(query: str, name: str, email: str, mobile: str):
    """Turn supported natural-language phrases into parameterized user filters."""
    filters = []
    parameters = {}
    query = query.strip()

    if name:
        filters.append("user_name ILIKE :name")
        parameters["name"] = f"%{name.strip()}%"
    if email:
        filters.append("user_email ILIKE :email")
        parameters["email"] = f"%{email.strip()}%"
    if mobile:
        filters.append("mobile_number ILIKE :mobile")
        parameters["mobile"] = f"%{mobile.strip()}%"

    if query:
        query_filters = []
        email_match = re.search(r"(?:email|mail)\s+(?:is|contains|for)?\s*([\w.+-]+@[\w.-]+)", query, re.IGNORECASE)
        mobile_match = re.search(r"(?:mobile|phone|number)\s+(?:is|contains|ending in)?\s*(\d+)", query, re.IGNORECASE)
        name_match = re.search(r"(?:name|named)\s+(?:is|contains)?\s*([A-Za-z][A-Za-z .'-]*)", query, re.IGNORECASE)

        if email_match:
            parameters["query_email"] = f"%{email_match.group(1)}%"
            query_filters.append("user_email ILIKE :query_email")
        if mobile_match:
            parameters["query_mobile"] = f"%{mobile_match.group(1)}%"
            query_filters.append("mobile_number ILIKE :query_mobile")
        if name_match:
            parameters["query_name"] = f"%{name_match.group(1).strip()}%"
            query_filters.append("user_name ILIKE :query_name")

        if not query_filters:
            parameters["query"] = f"%{query}%"
            query_filters.append(
                "(user_name ILIKE :query OR user_email ILIKE :query "
                "OR mobile_number ILIKE :query OR resume_loc ILIKE :query)"
            )
        filters.extend(query_filters)

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    return where_clause, parameters
