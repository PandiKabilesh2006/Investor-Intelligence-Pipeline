def unique_merge(list_a, list_b):

    combined = list_a + list_b

    seen = set()

    output = []


    for item in combined:

        normalized = (

            str(item)
            .strip()
            .lower()
        )


        if normalized in seen:

            continue


        seen.add(normalized)

        output.append(item)


    return output


# =========================================
# INVESTOR ENTITY MERGING
# =========================================

def merge_investor_entities(

    canonical,

    incoming
):

    merged = {

        "firm": (

            canonical.get("firm")

            or

            incoming.get("firm")
        ),

        "website": (

            canonical.get("website")

            or

            incoming.get("website")
        ),

        "focus_sectors": unique_merge(

            canonical.get(
                "focus_sectors",
                []
            ),

            incoming.get(
                "focus_sectors",
                []
            )
        ),

        "investment_stage": unique_merge(

            canonical.get(
                "investment_stage",
                []
            ),

            incoming.get(
                "investment_stage",
                []
            )
        ),

        "partners": unique_merge(

            canonical.get(
                "partners",
                []
            ),

            incoming.get(
                "partners",
                []
            )
        ),

        "portfolio_companies": unique_merge(

            canonical.get(
                "portfolio_companies",
                []
            ),

            incoming.get(
                "portfolio_companies",
                []
            )
        ),

        "geography": unique_merge(

            canonical.get(
                "geography",
                []
            ),

            incoming.get(
                "geography",
                []
            )
        ),

        "contact_links": unique_merge(

            canonical.get(
                "contact_links",
                []
            ),

            incoming.get(
                "contact_links",
                []
            )
        )
    }


    return merged