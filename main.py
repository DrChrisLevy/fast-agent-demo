# ruff: noqa: F403, F405

from dotenv import load_dotenv
from fasthtml.common import *

load_dotenv()


def before(req, sess):
    # Middleware runs before each request
    pass


beforeware = Beforeware(
    before,
    skip=[],
)

hdrs = (
    # DaisyUI + Tailwind
    Link(href="https://cdn.jsdelivr.net/npm/daisyui@5/daisyui.css", rel="stylesheet"),
    Link(href="https://cdn.jsdelivr.net/npm/daisyui@5/themes.css", rel="stylesheet"),
    Script(src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"),
    # HTMX SSE extension
    Script(src="https://unpkg.com/htmx-ext-sse@2.2.1/sse.js"),
)
app, rt = fast_app(
    before=beforeware,
    pico=False,
    hdrs=hdrs,
    htmlkw={"data-theme": "corporate"},
    secret_key=os.getenv("FAST_APP_SECRET"),
    max_age=365 * 24 * 3600,  # Session cookie expiry
)


@rt("/")
def index(req, sess):
    return Div(
        Div(
            Div(
                H1("JOO", cls="text-5xl font-bold text-primary"),
                P("Welcome to your agent dashboard", cls="py-4 text-base-content/70"),
                Button("Get Started", cls="btn btn-primary"),
                cls="max-w-md",
            ),
            cls="hero-content text-center",
        ),
        cls="hero min-h-screen bg-base-200",
    )


# from agents.agent import run_agent
# result = run_agent("What's the weather in Tokyo and what's 25 * 4?")
# print(result)

serve()
