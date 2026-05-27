def generate_queries(profile):

    sector = profile["sector"]

    subdomains = profile["subdomains"]

    stage = profile["stage"]

    geography = profile["geography"]

    queries = []

    for subdomain in subdomains:

        queries.extend([

            f"{subdomain} venture capital firms",

            f"{subdomain} startup investors",

            f"{subdomain} {stage} VC firms",

            f"{sector} {subdomain} investors",

            f"{subdomain} investors in {geography}"
        ])

    return list(set(queries))