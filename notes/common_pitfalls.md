# Common Pitfalls and Issues

This document is meant to share some of the common pitfalls, issues, and errors that we have encountered while helping others set up Riverst on their local systems and some possible ways to go about solving them.

## Google OAuth

We have noticed that even when all of the setup for Google OAuth has been done perfectly (creation in the web console, .env configured properly, authorized users listed), OAuth still might not work. Some notes about Google OAuth:

### It does not allow for connections without a DNS record (using IP addresses)

You might encounter this after having run it locally without issue since it is fine with using localhost, but moving it onto a server or attempting cross-machine connections might fail. There is currently not a workaround beyond giving your server a domain. Doing so will also help with other security related issues that are addressed later.

## Connecting Across Machines

Perhaps when you first put Riverst onto a server or boot it up locally and create a session, you might want to test it on another device. Despite it running fine locally, issues might occur when first attempting cross machine connections.

### Cannot find the dev machine/hosted site at all

In the case that you can't find the Riverst site at all from another machine, there are a few checks you can make:

- If you are using IP addresses, the machines likely need to be on the same local network, unless the IP address can be accessed from external networks.
- The dev server is typically binding to your localhost, but to allow for external connections, one can use `npm run dev -- --host 0.0.0.0`

## The site is reachable but the sessions are empty

This might have occurred for a number of reasons. Make sure to check the server logs as well as the browser logs. A notable error that we have found is `crypto.randomUUID is not a function`. On the surface this might seem like a versioning issue, but it is actually because the crypto package requires a secure context. This can either be through `https://` URLs or using `http://localhost` (or similarly `http://127.0.0.1`) which might have been why initial tests worked but when doing cross machine connections, things failed.

There are a few possible solutions for this. One is using ngrok or some other service to expose the local server over HTTPS. A quick workaround can also be to provide self-signed certificates. Any users will have to accept security warnings but this will allow cross machine connections.

Go to `src/client/react/`, open `vite.config.ts` add the following to `server` section:
```javascript
https: {
      key: fs.readFileSync('./cert/key.pem'),
      cert: fs.readFileSync('./cert/cert.pem'),
    }
```

You will also need to add `import fs from 'fs'` to the file imports.

Within that same folder, run the following:

```
mkdir cert
openssl req -x509 -newkey rsa:2048 -keyout cert/key.pem -out cert/cert.pem -days 365 -nodes
```
