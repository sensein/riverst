# Riverst client

## Requirements
-
- The server must be running before starting the client.

## Getting started
1. [Install npm](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm) on your local machine, if not there yet.

2. Install client-specific dependencies:
```bash
npm install
```

3. Configure environment variables:
   - Copy `.env.example` to `.env`
   - Set your env variables (you can follow the instructions in the `.env.example` file)

**Note**: Not all env variables are strictly required. Only if you want to use a remote service, you need to expose the corresponding variables
**Note**: `.env` is gitignored for security


4. Run the client app:
```
npm run dev
```

5. Visit http://localhost:5173 in your browser.

### Alternative approache to run the client script with Docker
```bash
docker build --no-cache -t react-frontend .
docker run -p 3000:80 react-frontend
```
