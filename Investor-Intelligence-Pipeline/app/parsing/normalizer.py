def normalize_partners(partners):

    normalized = []

    for partner in partners:

        # Already object
        if isinstance(partner, dict):

            normalized.append({
                "name": partner.get("name", ""),
                "role": partner.get("role", "")
            })

        # String only
        elif isinstance(partner, str):

            normalized.append({
                "name": partner,
                "role": ""
            })

    return normalized


def normalize_contact_links(contact_links):

    normalized = []

    for link in contact_links:

        # Already object
        if isinstance(link, dict):

            normalized.append({
                "type": link.get("type", ""),
                "value": link.get("value", "")
            })

        # Raw string
        elif isinstance(link, str):

            normalized.append({
                "type": "url",
                "value": link
            })

    return normalized


def normalize_investor_data(data):

    data["partners"] = normalize_partners(
        data.get("partners", [])
    )

    data["contact_links"] = normalize_contact_links(
        data.get("contact_links", [])
    )

    return data