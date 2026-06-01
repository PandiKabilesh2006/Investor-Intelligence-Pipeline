BLOCKED_URL_STATUS = "blocked"

BLOCKED_HTTP_STATUS_CODES = {
    401,
    403,
    407,
}

BLOCKED_ERROR_PATTERNS = [
    "access denied",
    "are you a human",
    "automated access",
    "blocked by",
    "bot detection",
    "bot verification",
    "captcha",
    "cf-browser-verification",
    "checking if the site connection is secure",
    "checking if you are human",
    "cloudflare",
    "ddos protection",
    "enable javascript",
    "forbidden",
    "human verification",
    "just a moment",
    "perimeterx",
    "please verify",
    "prove you are human",
    "robot check",
    "security check",
    "verify you are a human",
]

BLOCKED_REVIEW_REASON = (
    "Automated extraction appears blocked by bot protection, access controls, "
    "or a JavaScript verification wall. Use a manual source check, a public "
    "alternate page, or leave it blocked instead of retrying the same URL."
)
