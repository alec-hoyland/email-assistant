# LLM-powered Email Assistant API

Implements a straightforward personalized email assistant API.
The assistant uses OpenAI's GPT-4o model to help you write emails.

## How to use

```
git clone https://github.com/igorbenav/email-assistant-api.git
cd email-assistant-api
uv install
```

Then set up a `.env` file in `email-assistant-api/app`
with the following keys:

```
OPENAI_API_KEY="your_openai_api_key"
SECRET_KEY="your_secret_key"
```

Your secret key can be generated with `openssl rand --hex 32`.

To start the application, run:

```
uv run fastapi run
```

You can see the API docs at `localhost:8000/docs`.
