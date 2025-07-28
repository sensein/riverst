# React Implementation

Basic implementation using the [Pipecat React SDK](https://docs.pipecat.ai/client/react/introduction).

## Setup

1. Run the server first.

2. Install client dependencies:

```bash
npm install
```

3. Configure environment variables:
   - Copy `.env.example` to `.env`
   - Set your `VITE_GOOGLE_CLIENT_ID` with your Google OAuth client ID

4. Run the client app:

```
npm run dev
```

5. Visit http://localhost:5173 in your browser.



## Alternative approache to run the client script with Docker

```bash
docker build --no-cache -t react-frontend .
docker run -p 3000:80 react-frontend
```
